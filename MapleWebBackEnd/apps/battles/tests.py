from types import SimpleNamespace

from django.test import SimpleTestCase

from .services import BattleService
from .urls import urlpatterns


class BattleRoutingTests(SimpleTestCase):
    def test_unvalidated_start_endpoint_is_not_public(self):
        route_names = {pattern.name for pattern in urlpatterns}
        self.assertNotIn('start-battle', route_names)


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
