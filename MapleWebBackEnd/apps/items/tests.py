from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance, Combatant
from apps.characters.models import Character
from apps.inventory.models import AuroraLine, InventoryItem, PendingAuroraRoll
from apps.market.models import Listing, Trade, TradeItem
from apps.party.models import Party
from apps.users.models import GameUser

from .models import (
    AuroraLineCountConfig,
    AuroraLinePool,
    AuroraModifierRule,
    AuroraProperty,
    ItemTemplate,
)
from .serializers import ItemTemplateSerializer


class ItemTemplateAssetKeyTests(TestCase):
    def test_asset_keys_are_exposed_by_item_api_serializer(self):
        item = ItemTemplate.objects.create(
            name='Copper Bow',
            item_type='weapon',
            weapon_type='bow',
            icon_key='equipment.weapon.copper_bow.icon',
            visual_key='equipment.weapon.copper_bow',
        )

        data = ItemTemplateSerializer(item).data

        self.assertEqual(data['icon_key'], 'equipment.weapon.copper_bow.icon')
        self.assertEqual(data['visual_key'], 'equipment.weapon.copper_bow')


class EssenceAPITests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Essence Tester')
        self.user = GameUser.objects.create_user(
            username='essence-user', email='essence@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.aurora = AuroraProperty.objects.create(
            name='Test Aurora', tier=1, max_aurora_level=3
        )
        AuroraLineCountConfig.objects.create(min_item_level=0, max_lines=1)
        for level, value in [(1, 2), (2, 4), (3, 6)]:
            AuroraLinePool.objects.create(
                aurora_property=self.aurora,
                item_types=['weapon'],
                aurora_level=level,
                stat_type='att',
                line_type='flat',
                value=value,
                weight=1,
            )
        target_template = ItemTemplate.objects.create(
            name='Essence Target', item_type='weapon', aurora_tier=self.aurora
        )
        self.target = InventoryItem.objects.create(
            owner=self.character, template=target_template, aurora_level=1
        )
        AuroraLine.objects.create(
            inventory_item=self.target,
            line_index=0,
            stat_type='att',
            line_type='flat',
            value=1,
        )
        essence_template = ItemTemplate.objects.create(
            name='Test Essence', item_type='use'
        )
        self.rule = AuroraModifierRule.objects.create(
            item_template=essence_template,
            modifier_type='REROLL_ALL',
            max_aurora_target=3,
            tier_up_chance=0,
        )
        self.essence = InventoryItem.objects.create(
            owner=self.character, template=essence_template, quantity=2
        )
        self.modify_url = reverse('essence-apply')
        self.confirm_url = reverse('essence-confirm')

    def modify(self, **overrides):
        payload = {
            'target_item_id': self.target.id,
            'modifier_item_id': self.essence.id,
        }
        payload.update(overrides)
        return self.client.post(self.modify_url, payload, format='json')

    def test_essence_rerolls_and_returns_updated_item(self):
        response = self.modify()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['item']['id'], self.target.id)
        self.assertEqual(len(response.data['item']['aurora_lines']), 1)
        self.essence.refresh_from_db()
        self.assertEqual(self.essence.quantity, 1)

    def test_legacy_aurora_modify_route_remains_available(self):
        response = self.client.post(
            reverse('aurora-api', args=['modify']),
            {
                'target_item_id': self.target.id,
                'modifier_item_id': self.essence.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_or_ambiguous_payload_returns_http_400(self):
        missing_modifier = self.client.post(
            self.modify_url, {'target_item_id': self.target.id}, format='json'
        )
        ambiguous = self.modify(use_lumis=True)

        self.assertEqual(missing_modifier.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ambiguous.status_code, status.HTTP_400_BAD_REQUEST)

    def test_listed_target_or_modifier_cannot_be_changed_or_consumed(self):
        Listing.objects.create(seller=self.user, item=self.target, price=10)
        target_response = self.modify()
        self.assertEqual(target_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.essence.refresh_from_db()
        self.assertEqual(self.essence.quantity, 2)

        Listing.objects.filter(item=self.target).update(is_active=False)
        Listing.objects.create(
            seller=self.user, item=self.essence, price=10, quantity=1
        )
        modifier_response = self.modify()
        self.assertEqual(modifier_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.essence.refresh_from_db()
        self.assertEqual(self.essence.quantity, 2)

    def test_pending_trade_target_cannot_be_changed(self):
        receiver = GameUser.objects.create_user(
            username='essence-receiver', email='essence-receiver@example.com',
            password='test-pass-123'
        )
        trade = Trade.objects.create(sender=self.user, receiver=receiver)
        TradeItem.objects.create(trade=trade, item=self.target, is_sender=True)

        response = self.modify()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.essence.refresh_from_db()
        self.assertEqual(self.essence.quantity, 2)

    def test_destroyed_or_expired_items_are_rejected(self):
        self.target.is_destroyed = True
        self.target.save(update_fields=['is_destroyed'])
        destroyed_response = self.modify()
        self.assertEqual(destroyed_response.status_code, status.HTTP_400_BAD_REQUEST)

        self.target.is_destroyed = False
        self.target.save(update_fields=['is_destroyed'])
        self.essence.expired_at = timezone.now() - timedelta(seconds=1)
        self.essence.save(update_fields=['expired_at'])
        expired_response = self.modify()
        self.assertEqual(expired_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_essence_cannot_be_used_during_active_battle(self):
        party = Party.objects.create(name='Essence Party', leader=self.character)
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

        response = self.modify()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.essence.refresh_from_db()
        self.assertEqual(self.essence.quantity, 2)

    def test_choice_essence_requires_confirmation_and_returns_snapshot(self):
        self.rule.modifier_type = 'REROLL_CHOICE'
        self.rule.save(update_fields=['modifier_type'])
        roll_response = self.modify()
        self.assertEqual(roll_response.status_code, status.HTTP_200_OK)
        self.assertTrue(roll_response.data['pending'])
        self.assertTrue(PendingAuroraRoll.objects.filter(inventory_item=self.target).exists())

        confirm_response = self.client.post(
            self.confirm_url,
            {'inventory_item_id': self.target.id, 'action': 'take_new'},
            format='json',
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_response.data['item']['id'], self.target.id)
        self.assertFalse(PendingAuroraRoll.objects.filter(inventory_item=self.target).exists())
