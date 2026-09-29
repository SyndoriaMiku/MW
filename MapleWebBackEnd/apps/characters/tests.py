from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.classes.models import CharacterClass, Job
from apps.inventory.models import AuroraLine, InventoryItem
from apps.items.models import ItemTemplate, TimedBuffRule
from apps.market.models import Listing
from apps.users.models import GameUser
from apps.world.models import ExperienceTable

from .models import Character, CharacterBuff, EquipmentSlotConfig, EquippedItem, RateEvent
from .serializers import CharacterSerializer


class CharacterRequiredExpSerializerTests(TestCase):
    def test_returns_required_exp_for_next_level(self):
        ExperienceTable.objects.create(level=1, required_exp=15)
        character = Character.objects.create(name='Level Tester', level=1, current_exp=4)

        data = CharacterSerializer(character).data

        self.assertEqual(data['current_exp'], 4)
        self.assertEqual(data['required_exp'], 15)

    def test_returns_null_when_current_level_has_no_exp_configuration(self):
        character = Character.objects.create(name='Max Level Tester', level=100)

        data = CharacterSerializer(character).data

        self.assertIsNone(data['required_exp'])


class MinimumDamageTests(TestCase):
    def test_damage_below_one_after_rounding_becomes_one(self):
        warrior = CharacterClass.objects.create(name='Warrior', main_stat='str')
        # STR 10 x ATT 5 / 100 = 0.5, which rounds to 0.
        character = Character.objects.create(
            name='Rookie', character_class=warrior,
            job=Job.objects.create(name='Fighter', character_class=warrior),
            base_str=10, base_att=5,
        )

        self.assertEqual(character.total_damage, 1)
        self.assertEqual(
            character.damage_from(str_value=0, agi_value=0, int_value=0, att_value=0), 1
        )

    def test_character_without_a_job_also_deals_at_least_one(self):
        character = Character.objects.create(name='Jobless', base_att=0)

        self.assertEqual(character.total_damage, 1)

    def test_normal_damage_is_unchanged(self):
        warrior = CharacterClass.objects.create(name='Knight', main_stat='str')
        character = Character.objects.create(
            name='Veteran', character_class=warrior,
            job=Job.objects.create(name='Guard', character_class=warrior),
            base_str=30, base_att=50,
        )

        self.assertEqual(character.total_damage, 15)


class GainRateTests(TestCase):
    """EXP/Lumis/drop rates: 1.0 base plus equipment, the best buff per rate, and every active event."""

    def setUp(self):
        self.character = Character.objects.create(name='Rates')
        self.now = timezone.now()

    def buff(self, name, *, minutes=30, **bonuses):
        template = ItemTemplate.objects.create(name=name, item_type='use')
        return CharacterBuff.objects.create(
            character=self.character, source_template=template,
            started_at=self.now, expires_at=self.now + timedelta(minutes=minutes), **bonuses,
        )

    def equip(self, template):
        slot, _ = EquipmentSlotConfig.objects.get_or_create(
            slot_type='ring',
            defaults={'display_name': 'Ring', 'max_count': 4, 'allowed_item_types': ['ring']},
        )
        item = InventoryItem.objects.create(owner=self.character, template=template)
        EquippedItem.objects.create(
            character=self.character, slot=slot,
            slot_index=self.character.equipped_items.count(), item=item,
        )
        return item

    def rates(self):
        character = Character.objects.get(pk=self.character.pk)
        return (
            character.total_exp_rate, character.total_lumis_rate,
            character.total_drop_rate, character.total_epic_drop_rate,
        )

    def assert_rates(self, expected):
        for actual, wanted in zip(self.rates(), expected):
            self.assertAlmostEqual(actual, wanted)

    def test_rates_default_to_one(self):
        self.assert_rates((1.0, 1.0, 1.0, 1.0))

    def test_active_buff_adds_its_percentage_bonus(self):
        self.buff(
            'Charm', exp_rate_bonus=100, lumis_rate_bonus=50,
            drop_rate_bonus=20, epic_drop_rate_bonus=10,
        )

        self.assert_rates((2.0, 1.5, 1.2, 1.1))

    def test_different_buffs_on_the_same_rate_keep_the_highest(self):
        self.buff('Small EXP', exp_rate_bonus=50)
        self.buff('Big EXP', exp_rate_bonus=100, drop_rate_bonus=10)

        self.assert_rates((2.0, 1.0, 1.1, 1.0))

    def test_expired_buff_is_ignored(self):
        self.buff('Old Charm', minutes=-1, exp_rate_bonus=100)

        self.assert_rates((1.0, 1.0, 1.0, 1.0))

    def test_every_active_event_adds_on_top_of_buffs(self):
        self.buff('Charm', exp_rate_bonus=100)
        RateEvent.objects.create(name='Weekend', is_active=True, exp_rate_bonus=100)
        RateEvent.objects.create(name='Anniversary', is_active=True, exp_rate_bonus=50)
        RateEvent.objects.create(name='Switched off', is_active=False, exp_rate_bonus=500)
        RateEvent.objects.create(
            name='Over', is_active=True, end_time=self.now - timedelta(hours=1), exp_rate_bonus=500,
        )
        RateEvent.objects.create(
            name='Not yet', is_active=True, start_time=self.now + timedelta(hours=1), exp_rate_bonus=500,
        )

        self.assert_rates((3.5, 1.0, 1.0, 1.0))

    def test_equipment_drop_rate_boost_is_percentage_points(self):
        self.equip(ItemTemplate.objects.create(name='Lucky Ring', item_type='ring', drop_rate_boost=20))

        self.assert_rates((1.0, 1.0, 1.2, 1.0))

    def test_aurora_drop_line_is_percentage_points(self):
        ring = self.equip(ItemTemplate.objects.create(name='Aurora Ring', item_type='ring'))
        AuroraLine.objects.create(inventory_item=ring, stat_type='drop', line_type='percent', value=10)

        self.assert_rates((1.0, 1.0, 1.1, 1.0))

    def test_character_drop_rate_is_the_base(self):
        Character.objects.filter(pk=self.character.pk).update(drop_rate=1.5)
        self.buff('Drop Charm', drop_rate_bonus=20)

        self.assert_rates((1.0, 1.0, 1.7, 1.0))


class TimedBuffUseTests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Buffer')
        self.user = GameUser.objects.create_user(
            username='buffer', email='buffer@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.charm = ItemTemplate.objects.create(name='EXP Charm', item_type='use')
        TimedBuffRule.objects.create(
            item_template=self.charm, exp_rate_bonus=100,
            duration_minutes=30, max_duration_minutes=60,
        )
        self.stack = InventoryItem.objects.create(owner=self.character, template=self.charm, quantity=3)

    def use(self, item=None):
        return self.client.post(reverse('inventory-item-use', args=[(item or self.stack).pk]))

    def buff(self):
        return CharacterBuff.objects.get(character=self.character, source_template=self.charm)

    def assert_rejected(self, response, quantity=3):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.stack.refresh_from_db()
        self.assertEqual(self.stack.quantity, quantity)

    def test_using_a_buff_item_starts_the_buff_and_consumes_one(self):
        before = timezone.now()
        response = self.use()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['buff']['exp_rate_bonus'], 100)
        self.assertEqual(response.data['remaining_quantity'], 2)
        self.stack.refresh_from_db()
        self.assertEqual(self.stack.quantity, 2)
        buff = self.buff()
        self.assertGreaterEqual(buff.expires_at, before + timedelta(minutes=30))
        self.assertLessEqual(buff.expires_at, timezone.now() + timedelta(minutes=30))
        self.assertAlmostEqual(Character.objects.get(pk=self.character.pk).total_exp_rate, 2.0)

    def test_reusing_the_same_item_extends_the_remaining_time(self):
        self.use()
        first_expiry = self.buff().expires_at

        response = self.use()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.buff().expires_at, first_expiry + timedelta(minutes=30))
        self.assertEqual(CharacterBuff.objects.filter(character=self.character).count(), 1)

    def test_extension_past_the_maximum_duration_is_refused(self):
        self.use()
        self.use()

        self.assert_rejected(self.use(), quantity=1)

    def test_expired_buff_restarts_from_now(self):
        long_ago = timezone.now() - timedelta(days=1)
        CharacterBuff.objects.create(
            character=self.character, source_template=self.charm, exp_rate_bonus=100,
            started_at=long_ago, expires_at=long_ago + timedelta(minutes=30),
        )
        before = timezone.now()

        self.use()

        buff = self.buff()
        self.assertGreaterEqual(buff.started_at, before)
        self.assertGreaterEqual(buff.expires_at, before + timedelta(minutes=30))

    def test_different_buff_items_run_side_by_side(self):
        drop_charm = ItemTemplate.objects.create(name='Drop Charm', item_type='use')
        TimedBuffRule.objects.create(item_template=drop_charm, drop_rate_bonus=100, duration_minutes=30)
        drop_stack = InventoryItem.objects.create(owner=self.character, template=drop_charm)

        self.use()
        response = self.use(drop_stack)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CharacterBuff.objects.filter(character=self.character).count(), 2)
        self.assertFalse(InventoryItem.objects.filter(pk=drop_stack.pk).exists())

    def test_item_without_a_buff_rule_is_refused(self):
        snack = InventoryItem.objects.create(
            owner=self.character, template=ItemTemplate.objects.create(name='Snack', item_type='use'),
        )

        response = self.use(snack)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(InventoryItem.objects.filter(pk=snack.pk).exists())

    def test_reserved_or_expired_items_are_refused(self):
        Listing.objects.create(seller=self.user, item=self.stack, price=10)
        self.assert_rejected(self.use())

        Listing.objects.all().delete()
        self.stack.expired_at = timezone.now() - timedelta(seconds=1)
        self.stack.save(update_fields=['expired_at'])
        self.assert_rejected(self.use())

    def test_another_players_item_is_not_found(self):
        other = Character.objects.create(name='Other')
        foreign = InventoryItem.objects.create(owner=other, template=self.charm)

        response = self.use(foreign)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CharacterBuff.objects.exists())

    def test_character_payload_lists_active_buffs_and_rates(self):
        self.use()

        data = CharacterSerializer(Character.objects.get(pk=self.character.pk)).data

        self.assertEqual(len(data['active_buffs']), 1)
        self.assertEqual(data['active_buffs'][0]['item_template_id'], self.charm.pk)
        self.assertEqual(data['active_buffs'][0]['name'], 'EXP Charm')
        self.assertAlmostEqual(data['total_exp_rate'], 2.0)
        self.assertAlmostEqual(data['total_drop_rate'], 1.0)
