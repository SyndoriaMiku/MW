from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from apps.characters.models import Character, EquippedItem, EquipmentSlotConfig
from apps.items.models import ItemTemplate
from apps.market.models import Listing, Trade, TradeItem
from apps.users.models import GameUser

from .consumption_service import MaterialConsumptionError, consume_materials
from .admin import InventoryItemAdmin
from .models import InventoryItem


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
