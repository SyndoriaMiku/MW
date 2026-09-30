from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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
from .grant_service import grant_item
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

    def give_job(self, weapon_type):
        from apps.classes.models import CharacterClass, Job

        archer = CharacterClass.objects.create(name='Archer', main_stat='agi')
        self.character.character_class = archer
        self.character.job = Job.objects.create(name='Hunter', character_class=archer, weapon_type=weapon_type)
        self.character.save(update_fields=['character_class', 'job'])

    def weapon(self, weapon_type):
        template = ItemTemplate.objects.create(
            name=f'{weapon_type} weapon', item_type='weapon', weapon_type=weapon_type,
        )
        return InventoryItem.objects.create(owner=self.character, template=template)

    def equip(self, item):
        return self.client.post(self.equip_url(item), {'slot_index': 0}, format='json')

    def test_job_only_equips_its_own_weapon_type(self):
        self.give_job('bow')

        self.assertEqual(self.equip(self.weapon('staff')).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.equip(self.weapon('bow')).status_code, status.HTTP_200_OK)

    def test_weapon_type_does_not_limit_other_gear(self):
        self.give_job('bow')
        EquipmentSlotConfig.objects.create(slot_type='hat', display_name='Hat', allowed_item_types=['hat'])
        hat = InventoryItem.objects.create(
            owner=self.character, template=ItemTemplate.objects.create(name='Cap', item_type='hat'),
        )

        self.assertEqual(self.equip(hat).status_code, status.HTTP_200_OK)

    def test_character_without_a_job_or_job_without_a_type_equips_any_weapon(self):
        self.assertEqual(self.equip(self.weapon('staff')).status_code, status.HTTP_200_OK)

        self.give_job(None)
        self.assertEqual(self.equip(self.weapon('bow')).status_code, status.HTTP_200_OK)


class WeaponTypeValidationTests(TestCase):
    def test_weapons_need_a_type_and_other_items_must_not_have_one(self):
        from django.core.exceptions import ValidationError

        ItemTemplate(name='Bow', item_type='weapon', weapon_type='bow').full_clean()
        for fields in ({'item_type': 'weapon'}, {'item_type': 'hat', 'weapon_type': 'bow'}):
            with self.subTest(**fields), self.assertRaises(ValidationError):
                ItemTemplate(name='Broken', **fields).full_clean()


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

    def test_expired_item_is_not_consumed(self):
        expired = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=5,
            expired_at=timezone.now() - timedelta(seconds=1),
        )

        with self.assertRaises(MaterialConsumptionError):
            consume_materials(self.character, [
                {'item_template_id': self.material_a.id, 'quantity': 1},
            ])
        expired.refresh_from_db()
        self.assertEqual(expired.quantity, 5)


class GrantItemTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='GrantTester')
        self.user = GameUser.objects.create_user(
            username='grant-user', email='grant@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.potion = ItemTemplate.objects.create(name='Grant Potion', item_type='use')

    def stacks(self):
        return list(
            InventoryItem.objects.filter(owner=self.character, template=self.potion)
            .order_by('id').values_list('quantity', flat=True)
        )

    def test_equipment_gets_one_row_per_copy(self):
        sword = ItemTemplate.objects.create(name='Grant Sword', item_type='weapon')

        granted = grant_item(self.character, sword, 3)

        self.assertEqual(len(granted), 3)
        self.assertEqual(
            list(InventoryItem.objects.filter(template=sword).values_list('quantity', flat=True)),
            [1, 1, 1],
        )

    def test_stackable_creates_a_stack_then_merges_into_it(self):
        grant_item(self.character, self.potion, 2)
        grant_item(self.character, self.potion, 5)

        self.assertEqual(self.stacks(), [7])

    def test_several_existing_stacks_merge_into_the_oldest(self):
        InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=3)
        InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=4)

        grant_item(self.character, self.potion, 2)

        self.assertEqual(self.stacks(), [5, 4])

    def test_reserved_or_unusable_stacks_are_never_merged_into(self):
        receiver = GameUser.objects.create_user(
            username='grant-receiver', email='grant-receiver@example.com', password='test-pass-123'
        )
        listed = InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=1)
        Listing.objects.create(seller=self.user, item=listed, price=10, quantity=1)
        traded = InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=1)
        trade = Trade.objects.create(sender=self.user, receiver=receiver)
        TradeItem.objects.create(trade=trade, item=traded, is_sender=True)
        InventoryItem.objects.create(
            owner=self.character, template=self.potion, quantity=1, is_untrade=True
        )
        InventoryItem.objects.create(
            owner=self.character, template=self.potion, quantity=1,
            expired_at=timezone.now() + timedelta(days=1),
        )
        InventoryItem.objects.create(
            owner=self.character, template=self.potion, quantity=1, is_destroyed=True
        )

        granted = grant_item(self.character, self.potion, 4)

        self.assertEqual(self.stacks(), [1, 1, 1, 1, 1, 4])
        self.assertEqual(granted[0].quantity, 4)

    def test_untradeable_grant_only_merges_into_untradeable_stack(self):
        tradeable = InventoryItem.objects.create(
            owner=self.character, template=self.potion, quantity=2
        )
        bound = InventoryItem.objects.create(
            owner=self.character, template=self.potion, quantity=2, is_untrade=True
        )

        grant_item(self.character, self.potion, 3, is_untrade=True)

        tradeable.refresh_from_db()
        bound.refresh_from_db()
        self.assertEqual((tradeable.quantity, bound.quantity), (2, 5))

    def test_rejects_non_positive_quantity(self):
        for quantity in (0, -1, True):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    grant_item(self.character, self.potion, quantity)
        self.assertEqual(self.stacks(), [])


class SellToNpcTests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Seller')
        self.user = GameUser.objects.create_user(
            username='npc-seller', email='npc-seller@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)
        self.potion = ItemTemplate.objects.create(name='Sell Potion', item_type='use', sell_price=5)
        self.stack = InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=10)

    def sell(self, item, quantity=None):
        data = {} if quantity is None else {'quantity': quantity}
        return self.client.post(reverse('inventory-item-sell', args=[item.pk]), data, format='json')

    def test_selling_part_of_a_stack_pays_lumis(self):
        response = self.sell(self.stack, 4)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['lumis_gained'], 20)
        self.stack.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual((self.stack.quantity, self.user.lumis), (6, 20))

    def test_selling_the_whole_stack_removes_it(self):
        self.sell(self.stack, 10)

        self.assertFalse(InventoryItem.objects.filter(pk=self.stack.pk).exists())

    def test_rejects_unsellable_reserved_or_excess_quantities(self):
        bound = InventoryItem.objects.create(
            owner=self.character,
            template=ItemTemplate.objects.create(name='Quest Key', item_type='etc', is_sellable=False),
        )
        receiver = GameUser.objects.create_user(
            username='npc-rx', email='npc-rx@example.com', password='test-pass-123'
        )
        traded = InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=1)
        trade = Trade.objects.create(sender=self.user, receiver=receiver)
        TradeItem.objects.create(trade=trade, item=traded, is_sender=True)
        listed = InventoryItem.objects.create(owner=self.character, template=self.potion, quantity=1)
        Listing.objects.create(seller=self.user, item=listed, price=1)
        sword = InventoryItem.objects.create(
            owner=self.character,
            template=ItemTemplate.objects.create(name='Sell Sword', item_type='weapon'),
        )

        for item, quantity in ((bound, 1), (traded, 1), (listed, 1), (self.stack, 11), (sword, 2), (self.stack, 0)):
            with self.subTest(item=item.template.name, quantity=quantity):
                self.assertEqual(self.sell(item, quantity).status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.lumis, 0)

    def test_equipped_items_cannot_be_sold(self):
        sword = InventoryItem.objects.create(
            owner=self.character,
            template=ItemTemplate.objects.create(name='Worn Sword', item_type='weapon'),
        )
        slot = EquipmentSlotConfig.objects.create(
            slot_type='weapon', display_name='Weapon', allowed_item_types=['weapon']
        )
        EquippedItem.objects.create(character=self.character, slot=slot, item=sword)

        self.assertEqual(self.sell(sword).status_code, status.HTTP_400_BAD_REQUEST)


class EquipmentSlotAPITests(APITestCase):
    def test_lists_slot_configs_in_display_order(self):
        user = GameUser.objects.create_user(
            username='slot-viewer', email='slot-viewer@example.com', password='test-pass-123'
        )
        self.client.force_authenticate(user)
        EquipmentSlotConfig.objects.create(
            slot_type='ring', display_name='Ring', max_count=4, allowed_item_types=['ring'], order=2
        )
        EquipmentSlotConfig.objects.create(
            slot_type='hat', display_name='Hat', allowed_item_types=['hat'], order=1
        )

        response = self.client.get(reverse('equipment-slot-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {'id': response.data[0]['id'], 'slot_type': 'hat', 'display_name': 'Hat',
                 'max_count': 1, 'allowed_item_types': ['hat'], 'order': 1},
                {'id': response.data[1]['id'], 'slot_type': 'ring', 'display_name': 'Ring',
                 'max_count': 4, 'allowed_item_types': ['ring'], 'order': 2},
            ],
        )
