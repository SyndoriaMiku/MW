from datetime import datetime, timedelta
from unittest import mock

from django.db.models.query import QuerySet
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance
from apps.battles.services import BattleService
from apps.characters.models import Character
from apps.party.models import Party, PartyMember
from apps.reset_cycles import period_start
from apps.users.models import GameUser

from .models import (
    BossDungeonTemplate, BossStageEnemy, DungeonClearLog, EnemyTemplate, Location,
    NormalDungeonTemplate, Region,
)


class EnemyTemplateDisplayTests(SimpleTestCase):
    def test_admin_choice_uses_enemy_name(self):
        enemy = EnemyTemplate(name='Training Slime')

        self.assertEqual(str(enemy), 'Training Slime')


class BossDungeonFixture(APITestCase):
    """A party of one leader and a boss dungeon with one enemy."""

    def setUp(self):
        self.character = Character.objects.create(name='Boss Leader')
        self.user = GameUser.objects.create_user(
            username='boss-leader', email='boss-leader@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.party = Party.objects.create(name='Boss Party', leader=self.character)
        PartyMember.objects.create(party=self.party, character=self.character, position=1)
        boss = EnemyTemplate.objects.create(
            name='Boss', level=1, base_hp=100, base_mp=0, base_att=1,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        self.dungeon = BossDungeonTemplate.objects.create(name='Boss Lair')
        BossStageEnemy.objects.create(stage=self.dungeon, enemy=boss)
        self.url = reverse('boss-dungeon-enter', args=[self.dungeon.pk])


class BossDungeonEntryTests(BossDungeonFixture):
    def test_party_cannot_start_a_second_boss_battle(self):
        first = self.client.post(self.url)
        second = self.client.post(self.url)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CombatInstance.objects.filter(party=self.party).count(), 1)

    def test_entry_checks_run_under_a_party_row_lock(self):
        locked_models = []
        original = QuerySet.select_for_update

        def spy(queryset, *args, **kwargs):
            locked_models.append(queryset.model)
            return original(queryset, *args, **kwargs)

        with mock.patch.object(QuerySet, 'select_for_update', autospec=True, side_effect=spy):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(Party, locked_models)


class BossDungeonResetTests(BossDungeonFixture):
    """Boss clears reset on the calendar, like quests and shops."""

    def cleared(self, time_type, cleared_at):
        self.dungeon.time_type = time_type
        self.dungeon.save(update_fields=['time_type'])
        log = DungeonClearLog.objects.create(character=self.character, dungeon=self.dungeon)
        DungeonClearLog.objects.filter(pk=log.pk).update(cleared_at=cleared_at)

    def test_clear_from_the_previous_period_does_not_block(self):
        for time_type in ('daily', 'weekly', 'monthly'):
            with self.subTest(time_type=time_type):
                DungeonClearLog.objects.all().delete()
                CombatInstance.objects.all().delete()
                self.cleared(time_type, period_start(time_type) - timedelta(minutes=1))

                self.assertEqual(self.client.post(self.url).status_code, status.HTTP_200_OK)

    def test_clear_in_the_current_period_blocks(self):
        self.cleared('daily', period_start('daily'))

        self.assertEqual(self.client.post(self.url).status_code, status.HTTP_400_BAD_REQUEST)


class PeriodStartTests(SimpleTestCase):
    def test_period_boundaries(self):
        now = timezone.make_aware(datetime(2026, 9, 17, 15, 30))  # a Thursday

        self.assertEqual(period_start('daily', now), timezone.make_aware(datetime(2026, 9, 17)))
        self.assertEqual(period_start('weekly', now), timezone.make_aware(datetime(2026, 9, 14)))
        self.assertEqual(period_start('monthly', now), timezone.make_aware(datetime(2026, 9, 1)))


class WorldNavigationTests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Traveler', level=10)
        self.user = GameUser.objects.create_user(
            username='traveler', email='traveler@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.meadow = Region.objects.create(name='Meadow', order=1)
        self.peak = Region.objects.create(name='Peak', order=2, required_level=30)
        self.dungeon = NormalDungeonTemplate.objects.create(name='Slime Cave')
        self.town = Location.objects.create(name='Town', region=self.meadow, order=1, has_shop=True)
        self.cave = Location.objects.create(
            name='Cave', region=self.meadow, order=2, required_level=20, normal_dungeon=self.dungeon
        )
        self.summit = Location.objects.create(name='Summit', region=self.peak)

    def travel(self, location):
        return self.client.post(reverse('location-travel', args=[location.pk]))

    def test_regions_list_locations_with_access_and_dungeons(self):
        regions = self.client.get(reverse('region-list')).data

        self.assertEqual([r['name'] for r in regions], ['Meadow', 'Peak'])
        town, cave = regions[0]['locations']
        self.assertTrue(town['is_accessible'])
        self.assertTrue(town['has_shop'])
        self.assertFalse(cave['is_accessible'])
        self.assertEqual(cave['normal_dungeon'], {'id': self.dungeon.pk, 'name': 'Slime Cave'})
        self.assertFalse(regions[1]['locations'][0]['is_accessible'])

    def test_travel_updates_the_current_location(self):
        self.assertIsNone(self.client.get(reverse('location-current')).data['location'])

        response = self.travel(self.town)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_location, self.town)
        self.assertEqual(self.client.get(reverse('location-current')).data['location']['id'], self.town.pk)

    def test_travel_enforces_location_and_region_levels(self):
        for location in (self.cave, self.summit):
            with self.subTest(location=location.name):
                self.assertEqual(self.travel(location).status_code, status.HTTP_400_BAD_REQUEST)
        self.character.refresh_from_db()
        self.assertIsNone(self.character.current_location)

    def test_cannot_travel_during_a_battle(self):
        party = Party.objects.create(name='Travel Party', leader=self.character, max_size=1)
        PartyMember.objects.create(party=party, character=self.character, position=1)
        enemy = EnemyTemplate.objects.create(
            name='Road Slime', level=1, base_hp=10, base_mp=0, base_att=0,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        BattleService.start_combat(BattleService.create_combat_instance(party, [enemy]))

        self.assertEqual(self.travel(self.town).status_code, status.HTTP_400_BAD_REQUEST)
