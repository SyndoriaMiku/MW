from unittest import mock

from django.db.models.query import QuerySet
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance
from apps.characters.models import Character
from apps.party.models import Party, PartyMember
from apps.users.models import GameUser

from .models import BossDungeonTemplate, BossStageEnemy, EnemyTemplate


class EnemyTemplateDisplayTests(SimpleTestCase):
    def test_admin_choice_uses_enemy_name(self):
        enemy = EnemyTemplate(name='Training Slime')

        self.assertEqual(str(enemy), 'Training Slime')


class BossDungeonEntryTests(APITestCase):
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
