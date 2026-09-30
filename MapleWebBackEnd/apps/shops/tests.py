from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser

from .models import ShopCategory, ShopItem, SpecialShopItem, SpecialShopItemRecipe
from .serializers import MAX_QUANTITY_PER_REQUEST


class SpecialShopAtomicityTests(APITestCase):
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
        self.special_item = SpecialShopItem.objects.create(item=self.reward)
        SpecialShopItemRecipe.objects.create(
            recipe=self.special_item, item=self.material_a, quantity=3
        )
        SpecialShopItemRecipe.objects.create(
            recipe=self.special_item, item=self.material_b, quantity=2
        )
        self.url = reverse('special-shop-exchange', args=[self.special_item.id])

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
