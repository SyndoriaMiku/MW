from types import SimpleNamespace

from django.test import SimpleTestCase

from .services import BattleService
from .serializers import PlayerActionSerializer
from .urls import urlpatterns


class BattleRoutingTests(SimpleTestCase):
    def test_unvalidated_start_endpoint_is_not_public(self):
        route_names = {pattern.name for pattern in urlpatterns}
        self.assertNotIn('start-battle', route_names)

    def test_active_battle_endpoint_is_publicly_routed(self):
        route_names = {pattern.name for pattern in urlpatterns}
        self.assertIn('active-battle', route_names)


class PlayerActionContractTests(SimpleTestCase):
    def test_stable_target_id_is_accepted(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'ATTACK',
            'target_id': 42,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_legacy_target_position_remains_supported(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'ATTACK',
            'target_position': 5,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_target_is_required(self):
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
