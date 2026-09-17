from django.contrib.admin.sites import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance, Combatant
from apps.characters.models import Character, EquippedItem, EquipmentSlotConfig
from apps.items.models import (
    ItemSet, ItemSetEffect, ItemTemplate, LumenAscendRule, LumenTierProperty,
)
from apps.market.models import Listing, Trade, TradeItem
from apps.party.models import Party
from apps.users.models import GameUser

from .consumption_service import MaterialConsumptionError, consume_materials
from .admin import InventoryItemAdmin
from .models import InventoryItem
from .serializers import InventoryItemSerializer


class InventoryItemDisplayTests(TestCase):
    def test_admin_choice_uses_item_template_name(self):
        character = Character.objects.create(name='DisplayTester')
        template = ItemTemplate.objects.create(name='Copper Hammer', item_type='weapon')
        item = InventoryItem.objects.create(owner=character, template=template)

        self.assertEqual(str(item), 'Copper Hammer')

    def test_admin_shows_template_base_stats_and_edit_link(self):
        character = Character.objects.create(name='StatDisplayTester')
        template = ItemTemplate.objects.create(
            name='Copper Hammer', item_type='weapon', att_boost=12, str_boost=4
        )
        item = InventoryItem.objects.create(owner=character, template=template)

        rendered = str(InventoryItemAdmin(InventoryItem, AdminSite()).template_base_stats(item))

        self.assertIn('ATT: 12', rendered)
        self.assertIn('STR: 4', rendered)
        self.assertIn(f'/admin/items/itemtemplate/{template.pk}/change/', rendered)


class InventoryItemDetailSerializerTests(TestCase):
    def test_returns_item_sets_effects_and_applied_lumen_breakdown(self):
        character = Character.objects.create(name='Tooltip Tester')
        tier = LumenTierProperty.objects.create(
            name='Test Weapon Tier', tier=1, max_lumen_level=5
        )
        template = ItemTemplate.objects.create(
            name='Copper Bow', item_type='weapon', weapon_type='bow', lumen_tier=tier
        )
        item_set = ItemSet.objects.create(name='Copper Set', description='Starter equipment')
        item_set.items.add(template)
        ItemSetEffect.objects.create(
            item_set=item_set, required_count=2, att_boost=3, agi_boost=2
        )
        LumenAscendRule.objects.create(
            lumen_tier=tier, item_types=['weapon'], lumen_level=1, att_boost=2
        )
        LumenAscendRule.objects.create(
            lumen_tier=tier, item_types=['weapon'], lumen_level=2,
            att_boost=3, agi_boost=1
        )
        inventory_item = InventoryItem.objects.create(
            owner=character, template=template, lumen_ascend_level=2
        )

        data = InventoryItemSerializer(inventory_item).data

        self.assertEqual(data['template']['item_sets'][0]['name'], 'Copper Set')
        self.assertEqual(
            data['template']['item_sets'][0]['effects'][0]['required_count'], 2
        )
        self.assertEqual(
            data['template']['item_sets'][0]['effects'][0]['att_boost'], 3
        )
        self.assertEqual(len(data['lumen_breakdown']['levels']), 2)
        self.assertEqual(data['lumen_breakdown']['levels'][0]['stats']['att_boost'], 2)
        self.assertEqual(data['lumen_breakdown']['total']['att_boost'], 5)
        self.assertEqual(data['lumen_breakdown']['total']['agi_boost'], 1)

    def test_lumen_breakdown_is_empty_for_item_without_lumen_tier(self):
        character = Character.objects.create(name='Plain Item Tester')
        template = ItemTemplate.objects.create(name='Plain Hat', item_type='hat')
        inventory_item = InventoryItem.objects.create(owner=character, template=template)

        breakdown = InventoryItemSerializer(inventory_item).data['lumen_breakdown']

        self.assertIsNone(breakdown['tier'])
        self.assertEqual(breakdown['levels'], [])
        self.assertTrue(all(value == 0 for value in breakdown['total'].values()))


class EquipmentAPITests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Equipment Tester')
        self.user = GameUser.objects.create_user(
            username='equipment-user', email='equipment@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)
        self.slot = EquipmentSlotConfig.objects.create(
            slot_type='weapon', display_name='Weapon', allowed_item_types=['weapon']
        )
        self.template = ItemTemplate.objects.create(name='Test Sword', item_type='weapon')
        self.item = InventoryItem.objects.create(owner=self.character, template=self.template)

    def equip_url(self, item=None):
        return reverse('inventory-item-equip', args=[(item or self.item).pk])

    def unequip_url(self, item=None):
        return reverse('inventory-item-unequip', args=[(item or self.item).pk])

    def test_equip_replaces_slot_and_returns_current_snapshot(self):
        old_item = InventoryItem.objects.create(owner=self.character, template=self.template)
        EquippedItem.objects.create(
            character=self.character, slot=self.slot, slot_index=0, item=old_item
        )

        response = self.client.post(self.equip_url(), {'slot_index': 0}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['replaced_item_id'], old_item.id)
        self.assertEqual(response.data['equipped']['item']['id'], self.item.id)
        self.assertEqual(
            EquippedItem.objects.get(character=self.character, slot=self.slot).item_id,
            self.item.id,
        )

    def test_unequip_returns_item_snapshot(self):
        EquippedItem.objects.create(
            character=self.character, slot=self.slot, slot_index=0, item=self.item
        )

        response = self.client.post(self.unequip_url(), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['item']['id'], self.item.id)
        self.assertFalse(EquippedItem.objects.filter(item=self.item).exists())

    def test_null_slot_index_is_validation_error(self):
        response = self.client.post(
            self.equip_url(), {'slot_index': None}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_listed_item_cannot_be_equipped(self):
        Listing.objects.create(seller=self.user, item=self.item, price=10)

        response = self.client.post(self.equip_url(), {'slot_index': 0}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(EquippedItem.objects.filter(item=self.item).exists())

    def test_equipment_cannot_change_during_active_battle(self):
        party = Party.objects.create(name='Equipment Party', leader=self.character)
        combat = CombatInstance.objects.create(party=party)
        Combatant.objects.create(
            combat_instance=combat,
            content_type=ContentType.objects.get_for_model(self.character),
            objects_id=str(self.character.pk),
            is_player=True,
            current_hp=self.character.total_hp,
            current_mp=self.character.total_mp,
            position=1,
        )

        response = self.client.post(self.equip_url(), {'slot_index': 0}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(EquippedItem.objects.filter(item=self.item).exists())


class MaterialConsumptionTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='MaterialTester')
        self.user = GameUser.objects.create_user(
            username='material-user', email='material@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.material_a = ItemTemplate.objects.create(name='Material A', item_type='etc')
        self.material_b = ItemTemplate.objects.create(name='Material B', item_type='etc')

    def test_missing_later_requirement_does_not_consume_earlier_material(self):
        first_stack = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=3
        )

        with self.assertRaises(MaterialConsumptionError):
            consume_materials(self.character, [
                {'item_template_id': self.material_a.id, 'quantity': 3},
                {'item_template_id': self.material_b.id, 'quantity': 2},
            ])

        first_stack.refresh_from_db()
        self.assertEqual(first_stack.quantity, 3)

    def test_consumes_multiple_stacks_only_after_full_preflight(self):
        InventoryItem.objects.create(owner=self.character, template=self.material_a, quantity=2)
        remaining_stack = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=4
        )
        InventoryItem.objects.create(owner=self.character, template=self.material_b, quantity=1)

        consume_materials(self.character, [
            {'item_template_id': self.material_a.id, 'quantity': 5},
            {'item_template_id': self.material_b.id, 'quantity': 1},
        ])

        remaining_stack.refresh_from_db()
        self.assertEqual(remaining_stack.quantity, 1)
        self.assertFalse(
            InventoryItem.objects.filter(owner=self.character, template=self.material_b).exists()
        )

    def test_equipped_item_is_not_consumed(self):
        equipment_template = ItemTemplate.objects.create(name='Equipped Hat', item_type='hat')
        equipped_item = InventoryItem.objects.create(
            owner=self.character, template=equipment_template, quantity=1
        )
        slot = EquipmentSlotConfig.objects.create(
            slot_type='hat', display_name='Hat', allowed_item_types=['hat']
        )
        EquippedItem.objects.create(
            character=self.character, slot=slot, slot_index=0, item=equipped_item
        )

        with self.assertRaises(MaterialConsumptionError):
            consume_materials(self.character, [
                {'item_template_id': equipment_template.id, 'quantity': 1},
            ])
        self.assertTrue(InventoryItem.objects.filter(pk=equipped_item.pk).exists())

    def test_active_listing_item_is_not_consumed(self):
        listed_item = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=5
        )
        Listing.objects.create(seller=self.user, item=listed_item, price=10, quantity=5)

        with self.assertRaises(MaterialConsumptionError):
            consume_materials(self.character, [
                {'item_template_id': self.material_a.id, 'quantity': 1},
            ])
        listed_item.refresh_from_db()
        self.assertEqual(listed_item.quantity, 5)

    def test_pending_trade_item_is_not_consumed(self):
        receiver = GameUser.objects.create_user(
            username='material-receiver', email='receiver@example.com', password='test-pass-123'
        )
        traded_item = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=5
        )
        trade = Trade.objects.create(sender=self.user, receiver=receiver)
        TradeItem.objects.create(trade=trade, item=traded_item, is_sender=True)

        with self.assertRaises(MaterialConsumptionError):
            consume_materials(self.character, [
                {'item_template_id': self.material_a.id, 'quantity': 1},
            ])
        traded_item.refresh_from_db()
        self.assertEqual(traded_item.quantity, 5)
