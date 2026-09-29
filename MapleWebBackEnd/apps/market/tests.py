from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser

from .models import Listing
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
