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


class WorldLabelTests(APITestCase):
    """Regions and locations only name where dungeons are; they carry no gameplay."""

    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='mapreader', email='mapreader@example.com', password='test-pass-123'
        )
        self.client.force_authenticate(self.user)

        self.meadow = Region.objects.create(name='Meadow', order=1)
        self.peak = Region.objects.create(name='Peak', order=2)
        self.town = Location.objects.create(name='Town', region=self.meadow, order=1)
        self.summit = Location.objects.create(name='Summit', region=self.peak)
        self.cave = NormalDungeonTemplate.objects.create(name='Slime Cave', location=self.town, required_level=5)
        self.lair = BossDungeonTemplate.objects.create(name='Dragon Lair', location=self.summit, required_level=50)
        NormalDungeonTemplate.objects.create(name='Nowhere Dungeon')

    def test_regions_list_locations_with_their_dungeons(self):
        regions = self.client.get(reverse('region-list')).data

        self.assertEqual([r['name'] for r in regions], ['Meadow', 'Peak'])
        [town] = regions[0]['locations']
        self.assertEqual(town['normal_dungeons'], [{'id': self.cave.pk, 'name': 'Slime Cave', 'required_level': 5}])
        self.assertEqual(town['boss_dungeons'], [])
        self.assertEqual(regions[1]['locations'][0]['boss_dungeons'][0]['name'], 'Dragon Lair')

    def test_dungeons_name_their_location_and_region(self):
        dungeons = {d['name']: d for d in self.client.get(reverse('normal-dungeon-list')).data['results']}

        self.assertEqual(dungeons['Slime Cave']['location'], {
            'id': self.town.pk, 'name': 'Town', 'region': {'id': self.meadow.pk, 'name': 'Meadow'},
        })
        self.assertIsNone(dungeons['Nowhere Dungeon']['location'])

    def test_travel_endpoints_are_gone(self):
        from django.urls import NoReverseMatch

        for name, args in (('location-travel', [self.town.pk]), ('location-current', [])):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name, args=args)
