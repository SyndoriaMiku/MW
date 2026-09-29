from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser

from .models import Listing, Trade, TradeItem
from .views import ListingViewSet, TradeViewSet


class MarketMutationSurfaceTests(SimpleTestCase):
    def test_listing_does_not_expose_generic_update_methods(self):
        self.assertNotIn('put', ListingViewSet.http_method_names)
        self.assertNotIn('patch', ListingViewSet.http_method_names)

    def test_trade_changes_only_through_explicit_actions(self):
        self.assertNotIn('put', TradeViewSet.http_method_names)
        self.assertNotIn('patch', TradeViewSet.http_method_names)
        self.assertNotIn('delete', TradeViewSet.http_method_names)


class MarketStackPurchaseTests(APITestCase):
    def create_player(self, name):
        character = Character.objects.create(name=name)
        user = GameUser.objects.create_user(
            username=name, email=f'{name}@example.com', password='test-pass-123'
        )
        user.character = character
        user.lumis = 1000
        user.save(update_fields=['character', 'lumis'])
        return user, character

    def setUp(self):
        self.seller, self.seller_character = self.create_player('stack-seller')
        self.buyer, self.buyer_character = self.create_player('stack-buyer')
        self.potion = ItemTemplate.objects.create(name='Market Potion', item_type='use')
        self.seller_stack = InventoryItem.objects.create(
            owner=self.seller_character, template=self.potion, quantity=10
        )
        self.listing = Listing.objects.create(
            seller=self.seller, item=self.seller_stack, price=50, quantity=2
        )
        self.client.force_authenticate(self.buyer)

    def test_partial_stack_purchase_merges_into_buyer_stack(self):
        buyer_stack = InventoryItem.objects.create(
            owner=self.buyer_character, template=self.potion, quantity=3
        )

        response = self.client.post(reverse('listing-buy', args=[self.listing.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        buyer_stack.refresh_from_db()
        self.seller_stack.refresh_from_db()
        self.assertEqual(buyer_stack.quantity, 5)
        self.assertEqual(self.seller_stack.quantity, 8)
        self.assertEqual(
            InventoryItem.objects.filter(owner=self.buyer_character, template=self.potion).count(),
            1,
        )

    def test_trade_once_split_does_not_merge_into_tradeable_stack(self):
        self.potion.is_trade_once = True
        self.potion.save(update_fields=['is_trade_once'])
        buyer_stack = InventoryItem.objects.create(
            owner=self.buyer_character, template=self.potion, quantity=3
        )

        response = self.client.post(reverse('listing-buy', args=[self.listing.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        buyer_stack.refresh_from_db()
        self.assertEqual(buyer_stack.quantity, 3)
        bought = InventoryItem.objects.get(
            owner=self.buyer_character, template=self.potion, is_untrade=True
        )
        self.assertEqual(bought.quantity, 2)


class TradeLifecycleTests(APITestCase):
    def create_player(self, name):
        character = Character.objects.create(name=name)
        user = GameUser.objects.create_user(
            username=name, email=f'{name}@example.com', password='test-pass-123'
        )
        user.character = character
        user.save(update_fields=['character'])
        return user, character

    def setUp(self):
        self.alice, self.alice_character = self.create_player('trade-alice')
        self.bob, self.bob_character = self.create_player('trade-bob')
        self.sword_template = ItemTemplate.objects.create(name='Trade Sword', item_type='weapon')
        self.sword = InventoryItem.objects.create(
            owner=self.alice_character, template=self.sword_template
        )

    def as_user(self, user):
        self.client.force_authenticate(user)
        return self.client

    def open_trade(self, sender, receiver):
        response = self.as_user(sender).post(
            reverse('trade-list'), {'receiver_id': receiver.pk}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Trade.objects.get(pk=response.data['id'])

    def post(self, user, name, trade, data=None):
        return self.as_user(user).post(
            reverse(name, args=[trade.pk]), data or {}, format='json'
        )

    def complete_trade(self, trade):
        for user in (trade.sender, trade.receiver):
            self.post(user, 'trade-ready', trade)
        for user in (trade.sender, trade.receiver):
            response = self.post(user, 'trade-accept', trade)
        return response

    def test_item_received_in_a_trade_can_be_traded_again(self):
        first = self.open_trade(self.alice, self.bob)
        self.post(self.alice, 'trade-add-item', first, {'item_id': self.sword.pk})
        self.assertEqual(self.complete_trade(first).data['detail'], 'Trade successful.')

        second = self.open_trade(self.bob, self.alice)
        response = self.post(self.bob, 'trade-add-item', second, {'item_id': self.sword.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_either_participant_can_cancel_and_items_are_released(self):
        for canceller in (self.alice, self.bob):
            with self.subTest(canceller=canceller.username):
                trade = self.open_trade(self.alice, self.bob)
                self.post(self.alice, 'trade-add-item', trade, {'item_id': self.sword.pk})

                response = self.post(canceller, 'trade-cancel', trade)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                trade.refresh_from_db()
                self.assertEqual(trade.status, 'cancelled')
                self.assertFalse(
                    TradeItem.objects.filter(item=self.sword, trade__status='pending').exists()
                )

        listing = self.as_user(self.alice).post(
            reverse('listing-list'), {'item': self.sword.pk, 'price': 10}, format='json'
        )
        self.assertEqual(listing.status_code, status.HTTP_201_CREATED)

    def test_cancel_rejects_outsiders_and_finished_trades(self):
        outsider, _ = self.create_player('trade-outsider')
        trade = self.open_trade(self.alice, self.bob)

        self.assertEqual(
            self.post(outsider, 'trade-cancel', trade).status_code, status.HTTP_404_NOT_FOUND
        )
        self.post(self.alice, 'trade-cancel', trade)
        self.assertEqual(
            self.post(self.bob, 'trade-cancel', trade).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_owner_can_remove_item_and_other_party_is_unreadied(self):
        trade = self.open_trade(self.alice, self.bob)
        self.post(self.alice, 'trade-add-item', trade, {'item_id': self.sword.pk})
        self.post(self.bob, 'trade-ready', trade)

        response = self.post(self.alice, 'trade-remove-item', trade, {'item_id': self.sword.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        trade.refresh_from_db()
        self.assertFalse(trade.items.exists())
        self.assertFalse(trade.receiver_ready)

    def test_cannot_remove_other_party_item_or_while_ready(self):
        trade = self.open_trade(self.alice, self.bob)
        self.post(self.alice, 'trade-add-item', trade, {'item_id': self.sword.pk})

        other_party = self.post(self.bob, 'trade-remove-item', trade, {'item_id': self.sword.pk})
        self.post(self.alice, 'trade-ready', trade)
        while_ready = self.post(self.alice, 'trade-remove-item', trade, {'item_id': self.sword.pk})

        self.assertEqual(other_party.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(while_ready.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(trade.items.filter(item=self.sword).exists())
