from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser

from .models import SpecialShopItem, SpecialShopItemRecipe


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
