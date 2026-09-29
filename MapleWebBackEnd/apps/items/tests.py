from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance, Combatant
from apps.characters.models import Character, EquipmentSlotConfig, EquippedItem
from apps.inventory.models import AuroraLine, InventoryItem, PendingAuroraRoll
from apps.market.models import Listing, Trade, TradeItem
from apps.party.models import Party
from apps.users.models import GameUser

from .models import (
    AuroraLineCountConfig,
    AuroraLinePool,
    AuroraModifierRule,
    AuroraProperty,
    BattleConsumableRule,
    ItemTemplate,
    LumenCostRule,
    LumenEvent,
    LumenModifierRule,
    LumenTierProperty,
    TimedBuffRule,
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


class LumenPreviewAPITests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Lumen Preview Tester')
        self.user = GameUser.objects.create_user(
            username='lumen-preview-user',
            email='lumen-preview@example.com',
            password='test-pass-123',
        )
        self.user.character = self.character
        self.user.lumis = 750
        self.user.save(update_fields=['character', 'lumis'])
        self.client.force_authenticate(self.user)

        self.tier = LumenTierProperty.objects.create(
            name='Preview Tier', tier=91, max_lumen_level=5
        )
        self.rule = LumenCostRule.objects.create(
            lumen_tier=self.tier,
            current_level=0,
            lumis_cost=500,
            success_rate=0.7,
            failure_rate=0.2,
            heavy_failure_rate=0.1,
        )
        template = ItemTemplate.objects.create(
            name='Preview Sword',
            item_type='weapon',
            lumen_tier=self.tier,
        )
        self.item = InventoryItem.objects.create(
            owner=self.character,
            template=template,
        )
        self.url = reverse('lumen-api', args=['preview'])

    def preview(self, inventory_item_id=None):
        return self.client.get(
            self.url,
            {'inventory_item_id': inventory_item_id or self.item.id},
        )

    def test_preview_returns_cost_rates_outcomes_and_does_not_mutate(self):
        response = self.preview()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['cost'], {
            'currency': 'lumis',
            'amount': 500,
            'balance': 750,
            'can_afford': True,
        })
        self.assertEqual(response.data['base_rates'], {
            'success': 0.7,
            'failure': 0.2,
            'heavy_failure': 0.1,
        })
        self.assertEqual(response.data['final_rates'], {
            'success': 0.7,
            'failure': 0.2,
            'heavy_failure': 0.1,
        })
        self.assertEqual(response.data['final_rate_percent'], {
            'success': 70.0,
            'failure': 20.0,
            'heavy_failure': 10.0,
        })
        self.assertEqual(response.data['level']['on_success'], 1)
        self.assertEqual(
            response.data['outcomes']['heavy_failure'], 'item_destroyed'
        )

        self.user.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.user.lumis, 750)
        self.assertEqual(self.item.lumen_ascend_level, 0)
        self.assertFalse(self.item.is_destroyed)

    def test_preview_applies_current_event_modifiers(self):
        LumenEvent.objects.create(
            name='Preview Event',
            is_active=True,
            success_flat_bonus=0.1,
            heavy_failure_multiplier=0.5,
            bonus_levels=1,
        )

        response = self.preview()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['final_rates']['success'], 0.8)
        self.assertAlmostEqual(response.data['final_rates']['failure'], 0.15)
        self.assertEqual(response.data['final_rates']['heavy_failure'], 0.05)
        self.assertEqual(response.data['level']['on_success'], 2)
        self.assertEqual(
            response.data['event_modifiers']['active_events'][0]['name'],
            'Preview Event',
        )

    def test_preview_reports_when_balance_is_insufficient(self):
        self.user.lumis = 100
        self.user.save(update_fields=['lumis'])

        response = self.preview()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['cost']['can_afford'])
        self.assertEqual(response.data['cost']['balance'], 100)

    def test_preview_rejects_item_owned_by_another_player(self):
        other_character = Character.objects.create(name='Other Lumen Owner')
        other_item = InventoryItem.objects.create(
            owner=other_character,
            template=self.item.template,
        )

        response = self.preview(other_item.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])

    def test_preview_requires_a_valid_inventory_item_id(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inventory_item_id', response.data)


class LumenReservationAPITests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Lumen Guard Tester')
        self.user = GameUser.objects.create_user(
            username='lumen-guard-user', email='lumen-guard@example.com',
            password='test-pass-123',
        )
        self.user.character = self.character
        self.user.lumis = 1000
        self.user.save(update_fields=['character', 'lumis'])
        self.client.force_authenticate(self.user)

        tier = LumenTierProperty.objects.create(name='Guard Tier', tier=92, max_lumen_level=5)
        LumenCostRule.objects.create(
            lumen_tier=tier, current_level=0, lumis_cost=100, success_rate=1.0,
        )
        self.template = ItemTemplate.objects.create(
            name='Guard Hat', item_type='hat', lumen_tier=tier
        )
        self.item = InventoryItem.objects.create(owner=self.character, template=self.template)

    def ascend(self):
        return self.client.post(
            reverse('lumen-api', args=['ascend']),
            {'inventory_item_id': self.item.id}, format='json',
        )

    def restore(self, fragment, sacrifice):
        return self.client.post(
            reverse('lumen-api', args=['restore']),
            {'fragment_item_id': fragment.id, 'sacrifice_item_id': sacrifice.id},
            format='json',
        )

    def assert_ascend_blocked(self):
        response = self.ascend()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.item.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.item.lumen_ascend_level, 0)
        self.assertEqual(self.user.lumis, 1000)

    def test_listed_item_cannot_be_ascended_or_previewed(self):
        Listing.objects.create(seller=self.user, item=self.item, price=10)

        self.assert_ascend_blocked()
        preview = self.client.get(
            reverse('lumen-api', args=['preview']), {'inventory_item_id': self.item.id}
        )
        self.assertEqual(preview.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_in_pending_trade_cannot_be_ascended(self):
        receiver = GameUser.objects.create_user(
            username='lumen-guard-receiver', email='lumen-guard-receiver@example.com',
            password='test-pass-123',
        )
        trade = Trade.objects.create(sender=self.user, receiver=receiver)
        TradeItem.objects.create(trade=trade, item=self.item, is_sender=True)

        self.assert_ascend_blocked()

    def test_items_cannot_be_ascended_during_active_battle(self):
        party = Party.objects.create(name='Lumen Party', leader=self.character)
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

        self.assert_ascend_blocked()

    def test_reserved_sacrifice_is_not_consumed_by_restore(self):
        fragment = InventoryItem.objects.create(
            owner=self.character, template=self.template, is_destroyed=True
        )
        slot = EquipmentSlotConfig.objects.create(
            slot_type='hat', display_name='Hat', allowed_item_types=['hat']
        )
        receiver = GameUser.objects.create_user(
            username='restore-receiver', email='restore-receiver@example.com',
            password='test-pass-123',
        )

        def equip(item):
            EquippedItem.objects.create(character=self.character, slot=slot, item=item)

        def list_item(item):
            Listing.objects.create(seller=self.user, item=item, price=10)

        def offer_in_trade(item):
            trade = Trade.objects.create(sender=self.user, receiver=receiver)
            TradeItem.objects.create(trade=trade, item=item, is_sender=True)

        for reserve in (equip, list_item, offer_in_trade):
            with self.subTest(reservation=reserve.__name__):
                sacrifice = InventoryItem.objects.create(
                    owner=self.character, template=self.template
                )
                reserve(sacrifice)

                response = self.restore(fragment, sacrifice)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertTrue(InventoryItem.objects.filter(pk=sacrifice.pk).exists())
                fragment.refresh_from_db()
                self.assertTrue(fragment.is_destroyed)

    def test_restore_rejects_non_integer_ids(self):
        for data in (
            {'fragment_item_id': 'abc'},
            {'fragment_item_id': self.item.id, 'sacrifice_item_id': 'x'},
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    reverse('lumen-api', args=['restore']), data, format='json'
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_clean_sacrifice_still_restores_fragment(self):
        fragment = InventoryItem.objects.create(
            owner=self.character, template=self.template, is_destroyed=True
        )
        sacrifice = InventoryItem.objects.create(owner=self.character, template=self.template)

        response = self.restore(fragment, sacrifice)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fragment.refresh_from_db()
        self.assertFalse(fragment.is_destroyed)
        self.assertFalse(InventoryItem.objects.filter(pk=sacrifice.pk).exists())


class EssenceFixture(APITestCase):
    """A weapon with one revealed Aurora line and a stack of 2 essences."""

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


class EssenceAPITests(EssenceFixture):
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


class AuroraTierUpTests(EssenceFixture):
    """Tier-up belongs to the rolled result: kept or discarded with it."""

    def use_rule(self, modifier_type, **changes):
        for field, value in {'modifier_type': modifier_type, 'tier_up_chance': 1.0, **changes}.items():
            setattr(self.rule, field, value)
        self.rule.save()

    def confirm(self, action, **extra):
        return self.client.post(
            self.confirm_url,
            {'inventory_item_id': self.target.id, 'action': action, **extra},
            format='json',
        )

    def target_state(self):
        self.target.refresh_from_db()
        return self.target.aurora_level, list(self.target.aurora_lines.values_list('value', flat=True))

    def test_keeping_old_lines_discards_the_tier_up(self):
        self.use_rule('REROLL_CHOICE')

        rolled = self.modify()
        pending_state = self.target_state()
        self.confirm('keep_old')

        self.assertTrue(rolled.data['tier_up'])
        self.assertEqual(rolled.data['new_lines'][0]['value'], 4)
        self.assertEqual(pending_state, (1, [1]))
        self.assertEqual(self.target_state(), (1, [1]))

    def test_taking_new_lines_applies_the_tier_up(self):
        self.use_rule('REROLL_CHOICE')

        self.modify()
        self.confirm('take_new')

        self.assertEqual(self.target_state(), (2, [4]))

    def test_triple_choice_applies_the_tier_up_on_selection(self):
        self.use_rule('REROLL_TRIPLE_CHOICE')

        rolled = self.modify()
        self.confirm('select_specific', selected_temp_ids=[rolled.data['choices'][0]['temp_id']])

        self.assertTrue(rolled.data['tier_up'])
        self.assertEqual(self.target_state(), (2, [4]))

    def test_single_line_modifiers_never_tier_up(self):
        self.use_rule('REROLL_SINGLE')

        response = self.modify(target_line_index=0)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.target_state()[0], 1)

    def test_force_set_fills_every_line_without_tier_up(self):
        AuroraLineCountConfig.objects.update(max_lines=2)
        self.use_rule(
            'FORCE_SET', forced_aurora_level=2,
            fixed_stat_type='str', fixed_line_type='percent', fixed_value=5,
        )

        response = self.modify()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lines = list(self.target.aurora_lines.order_by('line_index').values_list('stat_type', 'value'))
        self.assertEqual(self.target_state()[0], 2)
        self.assertEqual(lines, [('str', 5), ('att', 4)])

    def test_rules_without_tier_up_reject_a_tier_up_chance(self):
        for modifier_type in ('REROLL_SINGLE', 'REPLACE_FIXED', 'FORCE_SET'):
            with self.subTest(modifier_type=modifier_type):
                self.rule.modifier_type = modifier_type
                self.rule.tier_up_chance = 0.5
                with self.assertRaises(ValidationError):
                    self.rule.clean()


class LumenLevelModifierTests(APITestCase):
    """Event items that set gear straight to a Lumen level: always succeed."""

    def setUp(self):
        self.character = Character.objects.create(name='Lumen Setter')
        self.user = GameUser.objects.create_user(
            username='lumen-setter', email='lumen-setter@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.tier = LumenTierProperty.objects.create(name='Set Tier', tier=93, max_lumen_level=10)
        self.hat_template = ItemTemplate.objects.create(
            name='Set Hat', item_type='hat', lumen_tier=self.tier
        )
        self.hat = InventoryItem.objects.create(
            owner=self.character, template=self.hat_template, lumen_ascend_level=2
        )
        scroll_template = ItemTemplate.objects.create(name='Lumen 7 Scroll', item_type='use')
        self.rule = LumenModifierRule.objects.create(item_template=scroll_template, target_level=7)
        self.scroll = InventoryItem.objects.create(
            owner=self.character, template=scroll_template, quantity=2
        )

    def apply(self, target=None):
        return self.client.post(
            reverse('lumen-api', args=['apply']),
            {'target_item_id': (target or self.hat).id, 'modifier_item_id': self.scroll.id},
            format='json',
        )

    def assert_rejected(self, response, level=2):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.hat.refresh_from_db()
        self.scroll.refresh_from_db()
        self.assertEqual((self.hat.lumen_ascend_level, self.scroll.quantity), (level, 2))

    def test_sets_the_level_and_consumes_one_item(self):
        response = self.apply()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['item']['lumen_ascend_level'], 7)
        self.scroll.refresh_from_db()
        self.assertEqual(self.scroll.quantity, 1)

    def test_never_lowers_the_level(self):
        self.hat.lumen_ascend_level = 7
        self.hat.save(update_fields=['lumen_ascend_level'])

        self.assert_rejected(self.apply(), level=7)

    def test_only_on_wearable_gear(self):
        self.hat.is_destroyed = True
        self.hat.save(update_fields=['is_destroyed'])
        self.assert_rejected(self.apply())

        self.hat.is_destroyed = False
        self.hat.expired_at = timezone.now() - timedelta(seconds=1)
        self.hat.save(update_fields=['is_destroyed', 'expired_at'])
        self.assert_rejected(self.apply())

    def test_respects_rule_tier_and_item_type_limits(self):
        other_tier = LumenTierProperty.objects.create(name='Other Tier', tier=94, max_lumen_level=10)
        self.rule.lumen_tiers.add(other_tier)
        self.assert_rejected(self.apply())

        self.rule.lumen_tiers.clear()
        self.rule.item_types = ['weapon']
        self.rule.save(update_fields=['item_types'])
        self.assert_rejected(self.apply())

    def test_cannot_exceed_the_tier_maximum(self):
        self.rule.target_level = 11
        self.rule.save(update_fields=['target_level'])

        self.assert_rejected(self.apply())

    def test_listed_gear_is_refused(self):
        Listing.objects.create(seller=self.user, item=self.hat, price=10)

        self.assert_rejected(self.apply())


class ItemUseKindTests(TestCase):
    def test_use_kind_follows_the_attached_rule(self):
        def template(name):
            return ItemTemplate.objects.create(name=name, item_type='use')

        potion, essence, scroll, charm, snack = (
            template(n) for n in ('Potion', 'Essence', 'Scroll', 'Charm', 'Snack')
        )
        BattleConsumableRule.objects.create(item_template=potion, hp_restore=10)
        AuroraModifierRule.objects.create(item_template=essence, modifier_type='REROLL_ALL')
        LumenModifierRule.objects.create(item_template=scroll, target_level=5)
        TimedBuffRule.objects.create(item_template=charm, exp_rate_bonus=100, duration_minutes=30)

        kinds = {
            t.name: ItemTemplateSerializer(t).data['use_kind']
            for t in (potion, essence, scroll, charm, snack)
        }

        self.assertEqual(kinds, {
            'Potion': 'battle', 'Essence': 'aurora_modifier', 'Scroll': 'lumen_modifier',
            'Charm': 'timed_buff', 'Snack': None,
        })


class DropRateUnitTests(TestCase):
    """Drop rate is always in percentage points, so Aurora drop lines may not be flat."""

    def setUp(self):
        self.aurora = AuroraProperty.objects.create(name='Drop Aurora', tier=1, max_aurora_level=3)

    def pool(self, line_type):
        return AuroraLinePool(
            aurora_property=self.aurora, item_types=['ring'], aurora_level=1,
            stat_type='drop', line_type=line_type, value=5,
        )

    def test_flat_drop_pool_line_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.pool('flat').full_clean()

        self.pool('percent').full_clean()

    def test_fixed_flat_drop_line_is_rejected(self):
        rule = AuroraModifierRule(
            item_template=ItemTemplate.objects.create(name='Drop Scroll', item_type='use'),
            modifier_type='REPLACE_FIXED',
            fixed_stat_type='drop', fixed_line_type='flat', fixed_value=5,
        )
        with self.assertRaises(ValidationError):
            rule.clean()

        rule.fixed_line_type = 'percent'
        rule.clean()


class TimedBuffRuleValidationTests(TestCase):
    def rule(self, item_type='use', **fields):
        fields.setdefault('duration_minutes', 30)
        return TimedBuffRule(
            item_template=ItemTemplate.objects.create(name='Charm', item_type=item_type), **fields,
        )

    def test_valid_rule_passes(self):
        self.rule(exp_rate_bonus=100, max_duration_minutes=60).full_clean()

    def test_only_use_items(self):
        with self.assertRaises(ValidationError):
            self.rule(item_type='ring', exp_rate_bonus=100).full_clean()

    def test_needs_a_bonus(self):
        with self.assertRaises(ValidationError):
            self.rule().full_clean()

    def test_maximum_cannot_be_shorter_than_one_use(self):
        with self.assertRaises(ValidationError):
            self.rule(exp_rate_bonus=100, max_duration_minutes=10).full_clean()
