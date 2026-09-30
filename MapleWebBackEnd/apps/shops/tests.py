from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser

from .models import (
    ShopCategory, ShopItem, SpecialShop, SpecialShopItem, SpecialShopItemRecipe, UserShopPurchase,
)
from .serializers import MAX_QUANTITY_PER_REQUEST


class SpecialShopFixture:
    """A permanent special shop whose reward costs 3 Material A + 2 Material B."""

    def setUp(self):
        self.character = Character.objects.create(name='ShopTester')
        self.user = GameUser.objects.create_user(
            username='shop-user', email='shop@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.material_a = ItemTemplate.objects.create(name='Shop Material A', item_type='etc')
        self.material_b = ItemTemplate.objects.create(name='Shop Material B', item_type='etc')
        self.reward = ItemTemplate.objects.create(name='Shop Reward', item_type='etc')
        self.shop = SpecialShop.objects.create(name='Permanent Exchange')
        self.special_item = SpecialShopItem.objects.create(shop=self.shop, item=self.reward)
        SpecialShopItemRecipe.objects.create(
            recipe=self.special_item, item=self.material_a, quantity=3
        )
        SpecialShopItemRecipe.objects.create(
            recipe=self.special_item, item=self.material_b, quantity=2
        )
        self.url = reverse('special-shop-exchange', args=[self.special_item.id])


class SpecialShopAtomicityTests(SpecialShopFixture, APITestCase):
    def test_missing_later_recipe_does_not_consume_earlier_material(self):
        material_a_stack = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=3
        )

        response = self.client.post(self.url, {'quantity': 1}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        material_a_stack.refresh_from_db()
        self.assertEqual(material_a_stack.quantity, 3)
        self.assertFalse(
            InventoryItem.objects.filter(owner=self.character, template=self.reward).exists()
        )

    def test_invalid_quantity_returns_400_without_mutation(self):
        response = self.client.post(self.url, {'quantity': 'not-a-number'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_successful_exchange_consumes_all_materials_and_grants_reward(self):
        InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=3
        )
        InventoryItem.objects.create(
            owner=self.character, template=self.material_b, quantity=2
        )

        response = self.client.post(self.url, {'quantity': 1}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            InventoryItem.objects.filter(
                owner=self.character,
                template_id__in=[self.material_a.id, self.material_b.id],
            ).exists()
        )
        reward_stack = InventoryItem.objects.get(owner=self.character, template=self.reward)
        self.assertEqual(reward_stack.quantity, 1)


class SpecialShopAvailabilityTests(SpecialShopFixture, APITestCase):
    """Permanent shops are always open; event shops only inside their window."""

    def setUp(self):
        super().setUp()
        InventoryItem.objects.create(owner=self.character, template=self.material_a, quantity=30)
        InventoryItem.objects.create(owner=self.character, template=self.material_b, quantity=20)
        self.now = timezone.now()

    def exchange(self):
        return self.client.post(self.url, {'quantity': 1}, format='json')

    def set_window(self, start, end):
        SpecialShop.objects.filter(pk=self.shop.pk).update(start_time=start, end_time=end)

    def listed_shops(self):
        return [shop['name'] for shop in self.client.get(reverse('special-shop-list-shops')).data]

    def test_event_shop_is_open_only_inside_its_window(self):
        hour = timedelta(hours=1)
        for start, end, open_ in [
            (self.now + hour, self.now + 2 * hour, False),   # not started
            (self.now - 2 * hour, self.now - hour, False),   # over
            (self.now - hour, self.now + hour, True),        # running
        ]:
            with self.subTest(start=start, end=end):
                self.set_window(start, end)
                expected = status.HTTP_200_OK if open_ else status.HTTP_400_BAD_REQUEST
                self.assertEqual(self.exchange().status_code, expected)
                self.assertEqual(self.listed_shops(), ['Permanent Exchange'] if open_ else [])

    def test_switched_off_shop_is_closed(self):
        SpecialShop.objects.filter(pk=self.shop.pk).update(is_active=False)

        self.assertEqual(self.exchange().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(reverse('special-shop-list')).data['results'], [])

    def test_shop_level_requirement(self):
        SpecialShop.objects.filter(pk=self.shop.pk).update(required_level=10)

        self.assertEqual(self.exchange().status_code, status.HTTP_400_BAD_REQUEST)

    def test_open_shops_list_their_items_and_event_window(self):
        self.set_window(self.now - timedelta(hours=1), self.now + timedelta(days=3))

        shop = self.client.get(reverse('special-shop-list-shops')).data[0]

        self.assertTrue(shop['is_event'])
        self.assertIsNotNone(shop['end_time'])
        self.assertEqual([item['id'] for item in shop['items']], [self.special_item.id])

    def test_end_must_follow_start(self):
        from django.core.exceptions import ValidationError

        shop = SpecialShop(name='Broken', start_time=self.now, end_time=self.now - timedelta(hours=1))
        with self.assertRaises(ValidationError):
            shop.full_clean()


class SpecialShopExchangeLimitTests(SpecialShopFixture, APITestCase):
    """Per-account exchange limits per item, reset by cycle and by a new event run."""

    def setUp(self):
        super().setUp()
        InventoryItem.objects.create(owner=self.character, template=self.material_a, quantity=300)
        InventoryItem.objects.create(owner=self.character, template=self.material_b, quantity=200)
        SpecialShopItem.objects.filter(pk=self.special_item.pk).update(exchange_limit=3)

    def exchange(self, quantity=1):
        return self.client.post(self.url, {'quantity': quantity}, format='json')

    def at(self, moment):
        return mock.patch('django.utils.timezone.now', return_value=moment)

    def test_limit_counts_every_exchange_of_the_item(self):
        self.assertEqual(self.exchange(2).status_code, status.HTTP_200_OK)
        self.assertEqual(self.exchange(2).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.exchange(1).status_code, status.HTTP_200_OK)
        self.assertEqual(self.exchange(1).status_code, status.HTTP_400_BAD_REQUEST)

        reward = InventoryItem.objects.get(owner=self.character, template=self.reward)
        self.assertEqual(reward.quantity, 3)

    def test_zero_means_unlimited(self):
        SpecialShopItem.objects.filter(pk=self.special_item.pk).update(exchange_limit=0)

        self.assertEqual(self.exchange(10).status_code, status.HTTP_200_OK)

    @override_settings(TIME_ZONE='UTC')
    def test_daily_limit_resets_the_next_day(self):
        SpecialShopItem.objects.filter(pk=self.special_item.pk).update(reset_cycle='daily')
        monday = datetime(2026, 3, 2, 10, tzinfo=dt_timezone.utc)

        with self.at(monday):
            self.exchange(3)
            self.assertEqual(self.exchange(1).status_code, status.HTTP_400_BAD_REQUEST)
        with self.at(monday + timedelta(days=1)):
            self.assertEqual(self.exchange(1).status_code, status.HTTP_200_OK)

    def test_a_new_run_of_an_event_shop_resets_the_count(self):
        first_run = datetime(2026, 3, 1, tzinfo=dt_timezone.utc)
        SpecialShop.objects.filter(pk=self.shop.pk).update(
            start_time=first_run, end_time=first_run + timedelta(days=7),
        )
        with self.at(first_run + timedelta(days=1)):
            self.exchange(3)
            self.assertEqual(self.exchange(1).status_code, status.HTTP_400_BAD_REQUEST)

        second_run = datetime(2026, 6, 1, tzinfo=dt_timezone.utc)
        SpecialShop.objects.filter(pk=self.shop.pk).update(
            start_time=second_run, end_time=second_run + timedelta(days=7),
        )
        with self.at(second_run + timedelta(days=1)):
            self.assertEqual(self.exchange(3).status_code, status.HTTP_200_OK)

    def test_items_show_the_limit_and_what_was_exchanged(self):
        self.exchange(2)

        item = self.client.get(reverse('special-shop-list')).data['results'][0]
        shop_item = self.client.get(reverse('special-shop-list-shops')).data[0]['items'][0]

        for data in (item, shop_item):
            self.assertEqual(
                (data['exchange_limit'], data['reset_cycle'], data['exchanged']), (3, 'none', 2),
            )


class ShopPurchaseStackTests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='StackShopper')
        self.user = GameUser.objects.create_user(
            username='stack-shopper', email='stack-shopper@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.lumis = 100
        self.user.save(update_fields=['character', 'lumis'])
        self.client.force_authenticate(self.user)

        self.potion = ItemTemplate.objects.create(name='Shop Potion', item_type='use')
        category = ShopCategory.objects.create(name='Potions')
        self.shop_item = ShopItem.objects.create(
            category=category, item_template=self.potion, price=5
        )

    def test_buying_when_character_owns_several_stacks_succeeds(self):
        oldest = InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=3)
        InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=2)

        response = self.client.post(
            reverse('shop-item-buy', args=[self.shop_item.id]), {'quantity': 4}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        oldest.refresh_from_db()
        self.assertEqual(oldest.quantity, 7)
        self.user.refresh_from_db()
        self.assertEqual(self.user.lumis, 80)

    def buy(self, quantity=1):
        return self.client.post(
            reverse('shop-item-buy', args=[self.shop_item.id]), {'quantity': quantity}, format='json'
        )

    def test_category_level_requirement_is_enforced(self):
        # Saved without clean(), as a direct DB edit could leave it.
        ShopCategory.objects.filter(pk=self.shop_item.category_id).update(required_level=10)

        self.assertEqual(self.buy().status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.lumis, 100)

    @override_settings(TIME_ZONE='UTC')
    def test_bought_count_uses_the_same_reset_calendar_as_the_limit(self):
        from datetime import datetime, timezone as dt_timezone
        from unittest import mock

        ShopItem.objects.filter(pk=self.shop_item.pk).update(stock=5, reset_cycle='weekly')
        purchase = UserShopPurchase.objects.create(user=self.user, shop_item=self.shop_item, quantity_bought=3)
        # Monday 2025-12-29 and Friday 2026-01-02 share a week (ISO week 1 of 2026).
        UserShopPurchase.objects.filter(pk=purchase.pk).update(
            last_purchased_at=datetime(2025, 12, 29, 10, tzinfo=dt_timezone.utc),
        )

        with mock.patch('django.utils.timezone.now', return_value=datetime(2026, 1, 2, 10, tzinfo=dt_timezone.utc)):
            shown = self.client.get(reverse('shop-item-detail', args=[self.shop_item.id])).data
            limited = self.buy(3)

        self.assertEqual(shown['current_bought'], 3)
        self.assertEqual(limited.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nova_purchase_is_recorded_in_the_ledger(self):
        from apps.users.models import NovaTransaction
        from apps.users.nova_service import change_nova

        change_nova(self.user, 50, NovaTransaction.Kind.DONATION, reference='kofi-shop')
        ShopCategory.objects.filter(pk=self.shop_item.category_id).update(currency_type='nova')

        self.assertEqual(self.buy(2).status_code, status.HTTP_200_OK)

        purchase = NovaTransaction.objects.get(kind=NovaTransaction.Kind.PURCHASE)
        self.assertEqual((purchase.amount, purchase.balance_after), (-10, 40))
        self.user.refresh_from_db()
        self.assertEqual(self.user.nova, 40)

    def test_quantity_per_purchase_is_capped(self):
        ShopItem.objects.filter(pk=self.shop_item.pk).update(price=0)

        self.assertEqual(self.buy(MAX_QUANTITY_PER_REQUEST + 1).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.buy(MAX_QUANTITY_PER_REQUEST).status_code, status.HTTP_200_OK)


class MalformedShopInputTests(APITestCase):
    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='shop-bad-input', email='shop-bad@example.com', password='test-pass-123'
        )
        self.user.character = Character.objects.create(name='ShopBadInput')
        self.user.lumis = 100
        self.user.save(update_fields=['character', 'lumis'])
        self.client.force_authenticate(self.user)
        category = ShopCategory.objects.create(name='Bad Input')
        self.shop_item = ShopItem.objects.create(
            category=category,
            item_template=ItemTemplate.objects.create(name='Bad Potion', item_type='use'),
            price=1,
        )

    def test_buy_rejects_non_integer_quantity(self):
        for quantity in ('abc', 1.5, 0):
            with self.subTest(quantity=quantity):
                response = self.client.post(
                    reverse('shop-item-buy', args=[self.shop_item.id]),
                    {'quantity': quantity}, format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(InventoryItem.objects.exists())

    def test_category_filter_rejects_non_integer(self):
        response = self.client.get(reverse('shop-item-list'), {'category': 'abc'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
