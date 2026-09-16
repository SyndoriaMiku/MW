from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.party.models import Party, PartyMember
from apps.users.models import GameUser
from apps.world.models import EnemyTemplate

from .serializers import PlayerActionSerializer
from .services import BattleService
from .urls import urlpatterns


class BattleRoutingTests(SimpleTestCase):
    def test_unvalidated_start_endpoint_is_not_public(self):
        route_names = {pattern.name for pattern in urlpatterns}
        self.assertNotIn('start-battle', route_names)

    def test_active_battle_endpoint_is_routed(self):
        route_names = {pattern.name for pattern in urlpatterns}
        self.assertIn('active-battle', route_names)


class PlayerActionContractTests(SimpleTestCase):
    def test_accepts_stable_target_id(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'ATTACK',
            'target_id': 42,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_keeps_legacy_target_position(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'ATTACK',
            'target_position': 5,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_requires_a_target(self):
        serializer = PlayerActionSerializer(data={'action_type': 'ATTACK'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('target_id', serializer.errors)


class BattleTargetValidationTests(SimpleTestCase):
    @staticmethod
    def combatant(pk, is_player):
        return SimpleNamespace(pk=pk, is_player=is_player)

    def test_enemy_skill_target_must_be_on_opposing_side(self):
        player = self.combatant(1, True)
        ally = self.combatant(2, True)
        enemy = self.combatant(3, False)

        self.assertTrue(BattleService._is_valid_skill_target(player, enemy, 'ENEMY'))
        self.assertFalse(BattleService._is_valid_skill_target(player, ally, 'ENEMY'))

    def test_self_and_ally_targets_are_enforced(self):
        player = self.combatant(1, True)
        ally = self.combatant(2, True)
        enemy = self.combatant(3, False)

        self.assertTrue(BattleService._is_valid_skill_target(player, player, 'SELF'))
        self.assertFalse(BattleService._is_valid_skill_target(player, ally, 'SELF'))
        self.assertTrue(BattleService._is_valid_skill_target(player, ally, 'ALLY'))
        self.assertFalse(BattleService._is_valid_skill_target(player, enemy, 'ALLY'))


class NormalAttackSceneContractTests(APITestCase):
    def setUp(self):
        self.character = Character.objects.create(name='BattleTester')
        self.user = GameUser.objects.create_user(
            username='battle-user', email='battle@example.com', password='test-pass-123'
        )
        self.user.character = self.character
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

        self.party = Party.objects.create(name='Test Party', leader=self.character, max_size=1)
        PartyMember.objects.create(party=self.party, character=self.character, position=1)

    def create_battle(self, *, enemy_hp=20, enemy_attack=2):
        enemy = EnemyTemplate.objects.create(
            name='Training Slime',
            level=1,
            base_hp=enemy_hp,
            base_mp=0,
            base_att=enemy_attack,
            exp_reward=0,
            lumis_reward_min=0,
            lumis_reward_max=0,
        )
        combat = BattleService.create_combat_instance(self.party, [enemy])
        BattleService.start_combat(combat)
        return combat

    def test_normal_attack_returns_player_and_monster_events_with_snapshot(self):
        combat = self.create_battle()
        target = combat.combatants.get(is_player=False)

        response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['events']), 2)
        self.assertEqual(response.data['events'][0]['actor_type'], 'character')
        self.assertEqual(response.data['events'][0]['target_id'], target.id)
        self.assertEqual(response.data['events'][1]['actor_type'], 'enemy')
        self.assertEqual(response.data['combat']['turn_count'], 2)

        player_snapshot = next(
            item for item in response.data['combat']['combatants'] if item['is_player']
        )
        enemy_snapshot = next(
            item for item in response.data['combat']['combatants'] if not item['is_player']
        )
        self.assertTrue(player_snapshot['is_current_actor'])
        self.assertEqual(player_snapshot['valid_actions'], ['ATTACK'])
        self.assertEqual(enemy_snapshot['id'], target.id)

    def test_finishing_attack_returns_victory_and_rewards(self):
        combat = self.create_battle(enemy_hp=1)
        target = combat.combatants.get(is_player=False)

        response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['combat']['status'], 'victory')
        self.assertEqual(response.data['events'][0]['battle_result']['status'], 'victory')
        self.assertIsNotNone(response.data['events'][0]['battle_result']['rewards'])

    def test_active_battle_can_restore_scene(self):
        combat = self.create_battle()

        response = self.client.get(reverse('battles:active-battle'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], combat.id)
        self.assertEqual(len(response.data['combatants']), 2)

    def test_active_battle_restores_latest_persisted_turn_state(self):
        combat = self.create_battle(enemy_hp=30, enemy_attack=3)
        target = combat.combatants.get(is_player=False)
        action_response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id},
            format='json',
        )
        self.assertEqual(action_response.status_code, status.HTTP_200_OK)

        response = self.client.get(reverse('battles:active-battle'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['turn_count'], action_response.data['combat']['turn_count'])
        self.assertEqual(response.data['combatants'], action_response.data['combat']['combatants'])

    def test_active_battle_returns_encounter_metadata(self):
        combat = self.create_battle()

        response = self.client.get(reverse('battles:active-battle'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['encounter'], {
            'type': 'custom', 'id': None, 'name': None,
        })

    def test_active_battle_returns_204_when_scene_does_not_exist(self):
        response = self.client.get(reverse('battles:active-battle'))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
