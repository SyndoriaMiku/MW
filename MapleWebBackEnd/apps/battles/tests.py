from types import SimpleNamespace

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character, CharacterSkill
from apps.party.models import Party, PartyMember
from apps.users.models import GameUser
from apps.world.models import EnemyTemplate, NormalDungeonTemplate, NormalStageEnemy
from apps.skilles.models import EffectTemplate, SkillLevelConfig, SkillTemplate

from .models import ActiveEffect, CombatInstance
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

    def test_skill_action_accepts_character_skill_id(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'SKILL',
            'target_id': 42,
            'character_skill_id': 7,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['character_skill_id'], 7)

    def test_skill_action_keeps_legacy_skill_id_alias(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'SKILL',
            'target_id': 42,
            'skill_id': 7,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['character_skill_id'], 7)

    def test_skill_action_allows_server_resolved_target_scope(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'SKILL',
            'character_skill_id': 7,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_skill_action_rejects_conflicting_ids(self):
        serializer = PlayerActionSerializer(data={
            'action_type': 'SKILL',
            'target_id': 42,
            'character_skill_id': 7,
            'skill_id': 8,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('character_skill_id', serializer.errors)


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

    def create_multi_enemy_battle(self, count=3, *, enemy_hp=100, enemy_attack=0):
        enemy = EnemyTemplate.objects.create(
            name='Slime Group',
            level=1,
            base_hp=enemy_hp,
            base_mp=20,
            base_att=enemy_attack,
            exp_reward=0,
            lumis_reward_min=0,
            lumis_reward_max=0,
        )
        combat = BattleService.create_combat_instance(self.party, [enemy] * count)
        BattleService.start_combat(combat)
        return combat

    def create_owned_skill(self, *, name, target_type, effect_type='DAMAGE', **kwargs):
        skill = SkillTemplate.objects.create(
            name=name,
            target_type=target_type,
            effect_type=effect_type,
            **kwargs,
        )
        owned = CharacterSkill.objects.create(
            character=self.character,
            skill_template=skill,
            level=1,
        )
        return skill, owned

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

    def test_owned_skill_is_discoverable_and_cast_by_character_skill_id(self):
        skill = SkillTemplate.objects.create(
            name='Power Shot',
            mp_cost=1,
            cooldown=2,
            target_type='ENEMY',
            effect_type='DAMAGE',
            base_power=4,
            power_ratio=1.0,
            icon_key='skill.bowman.power_shot.icon',
            visual_key='skill.bowman.power_shot',
        )
        SkillLevelConfig.objects.create(
            skill=skill,
            skill_level=1,
            required_char_level=1,
            damage_multiplier=1.5,
        )
        owned = CharacterSkill.objects.create(
            character=self.character,
            skill_template=skill,
            level=1,
        )
        combat = self.create_battle(enemy_hp=100)
        target = combat.combatants.get(is_player=False)

        snapshot = self.client.get(reverse('battles:active-battle'))
        player = next(c for c in snapshot.data['combatants'] if c['is_player'])
        self.assertIn('SKILL', player['valid_actions'])
        self.assertEqual(player['skills'][0]['character_skill_id'], owned.id)
        self.assertTrue(player['skills'][0]['can_use'])

        response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {
                'action_type': 'SKILL',
                'target_id': target.id,
                'character_skill_id': owned.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['action_log']['character_skill_id'], owned.id)
        self.assertEqual(response.data['action_log']['skill_template_id'], skill.id)
        self.assertEqual(
            response.data['action_log']['skill_visual_key'],
            'skill.bowman.power_shot',
        )

    def test_enemy_area_skill_hits_every_living_enemy_and_charges_once(self):
        skill, owned = self.create_owned_skill(
            name='Arrow Rain',
            target_type='E_AREA',
            base_power=10,
            power_ratio=0,
            mp_cost=4,
            cooldown=2,
        )
        combat = self.create_multi_enemy_battle(count=3)
        player = combat.combatants.get(is_player=True)
        mp_before = player.current_mp

        response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {
                'action_type': 'SKILL',
                'character_skill_id': owned.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = response.data['action_log']
        self.assertTrue(log['success'])
        self.assertEqual(log['skill_target_type'], 'E_AREA')
        self.assertEqual(len(log['targets']), 3)
        self.assertEqual(log['total_damage'], 30)
        self.assertEqual({item['damage'] for item in log['targets']}, {10})
        self.assertEqual(
            list(combat.combatants.filter(is_player=False).values_list('current_hp', flat=True)),
            [90, 90, 90],
        )
        player.refresh_from_db()
        self.assertEqual(player.current_mp, mp_before - skill.mp_cost)
        # The endpoint completes the monster phase and starts the next round,
        # which decrements the newly assigned cooldown exactly once.
        self.assertEqual(player.skill_cooldowns[str(skill.id)], skill.cooldown - 1)

    def test_two_turn_cooldown_can_be_reused_on_the_third_player_turn(self):
        _, owned = self.create_owned_skill(
            name='Cooldown Test Skill',
            target_type='E_AREA',
            base_power=1,
            power_ratio=0,
            cooldown=2,
        )
        combat = self.create_multi_enemy_battle(count=1)

        first_cast = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'SKILL', 'character_skill_id': owned.id},
            format='json',
        )
        self.assertTrue(first_cast.data['action_log']['success'])
        self.assertEqual(first_cast.data['combat']['turn_count'], 2)

        blocked_cast = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'SKILL', 'character_skill_id': owned.id},
            format='json',
        )
        self.assertFalse(blocked_cast.data['action_log']['success'])
        self.assertEqual(blocked_cast.data['combat']['turn_count'], 2)

        enemy_id = combat.combatants.get(is_player=False).id
        normal_attack = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': enemy_id},
            format='json',
        )
        self.assertEqual(normal_attack.data['combat']['turn_count'], 3)

        third_turn_cast = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'SKILL', 'character_skill_id': owned.id},
            format='json',
        )
        self.assertTrue(third_turn_cast.data['action_log']['success'])

    def test_ally_area_heal_applies_to_every_living_ally(self):
        self.party.max_size = 2
        self.party.save(update_fields=['max_size'])
        ally = Character.objects.create(name='Battle Ally')
        PartyMember.objects.create(party=self.party, character=ally, position=2)
        _, owned = self.create_owned_skill(
            name='Recovery Field',
            target_type='A_AREA',
            effect_type='HEAL',
            base_power=5,
            power_ratio=0,
        )
        combat = self.create_multi_enemy_battle(count=1)
        players = list(combat.combatants.filter(is_player=True).order_by('position'))
        for player in players:
            player.current_hp = 1
            player.save(update_fields=['current_hp'])

        log = BattleService.execute_action(
            players[0], 'SKILL', character_skill_id=owned.id
        )

        self.assertTrue(log['success'])
        self.assertEqual(len(log['targets']), 2)
        self.assertEqual(log['total_heal'], 10)
        self.assertTrue(all(item['target_type'] == 'character' for item in log['targets']))
        for player in players:
            player.refresh_from_db()
            self.assertEqual(player.current_hp, 6)

    def test_global_skill_hits_all_living_combatants_on_both_sides(self):
        skill, owned = self.create_owned_skill(
            name='Cataclysm',
            target_type='GLOBAL',
            base_power=7,
            power_ratio=0,
            mp_cost=3,
        )
        combat = self.create_multi_enemy_battle(count=2)
        player = combat.combatants.get(is_player=True)
        hp_before = {
            combatant.id: combatant.current_hp
            for combatant in combat.combatants.all()
        }
        mp_before = player.current_mp

        log = BattleService.execute_action(
            player, 'SKILL', character_skill_id=owned.id
        )

        self.assertTrue(log['success'])
        self.assertEqual(log['skill_target_type'], 'GLOBAL')
        self.assertEqual(len(log['targets']), 3)
        self.assertEqual(log['total_damage'], 21)
        self.assertEqual(
            {item['target_type'] for item in log['targets']},
            {'character', 'enemy'},
        )
        for combatant in combat.combatants.all():
            self.assertEqual(combatant.current_hp, hp_before[combatant.id] - 7)
        player.refresh_from_db()
        self.assertEqual(player.current_mp, mp_before - skill.mp_cost)

    def test_enemy_area_skill_hits_all_living_players(self):
        self.party.max_size = 2
        self.party.save(update_fields=['max_size'])
        ally = Character.objects.create(name='Enemy AOE Target')
        PartyMember.objects.create(party=self.party, character=ally, position=2)
        skill = SkillTemplate.objects.create(
            name='Monster Roar',
            availability='ENEMY',
            target_type='E_AREA',
            effect_type='DAMAGE',
            base_power=4,
            power_ratio=0,
        )
        combat = self.create_multi_enemy_battle(count=1)
        enemy = combat.combatants.get(is_player=False)
        players = list(combat.combatants.filter(is_player=True))
        hp_before = {player.id: player.current_hp for player in players}

        log = BattleService.execute_action(
            enemy, 'SKILL', skill_template_id=skill.id
        )

        self.assertTrue(log['success'])
        self.assertEqual(len(log['targets']), 2)
        self.assertTrue(all(item['target_type'] == 'character' for item in log['targets']))
        for player in players:
            player.refresh_from_db()
            self.assertEqual(player.current_hp, hp_before[player.id] - 4)

    def test_area_effect_is_applied_independently_to_every_target(self):
        burn = EffectTemplate.objects.create(
            name='Burning',
            duration_turns=3,
            hp_change_per_turn=-2,
        )
        _, owned = self.create_owned_skill(
            name='Ignite Field',
            target_type='E_AREA',
            effect_type='EFFECT',
            applies_effect=burn,
        )
        combat = self.create_multi_enemy_battle(count=3)
        player = combat.combatants.get(is_player=True)

        log = BattleService.execute_action(
            player, 'SKILL', character_skill_id=owned.id
        )

        enemy_ids = set(
            combat.combatants.filter(is_player=False).values_list('id', flat=True)
        )
        self.assertTrue(log['success'])
        self.assertEqual(len(log['targets']), 3)
        self.assertEqual(
            set(ActiveEffect.objects.values_list('target_id', flat=True)),
            enemy_ids,
        )
        self.assertEqual(
            set(item['effect'] for item in log['targets']),
            {'Burning'},
        )

    def test_percentage_dot_ticks_from_caster_damage_for_configured_duration(self):
        self.character.base_att = 40
        self.character.save(update_fields=['base_att'])
        ignite = EffectTemplate.objects.create(
            name='Ignite',
            duration_turns=3,
            damage_power_ratio_per_turn=0.25,
        )
        _, owned = self.create_owned_skill(
            name='Fire Ball',
            target_type='E_AREA',
            effect_type='DAMAGE',
            base_power=0,
            power_ratio=0,
            applies_effect=ignite,
        )
        combat = self.create_multi_enemy_battle(count=1, enemy_hp=100)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        BattleService.execute_action(
            player, 'SKILL', character_skill_id=owned.id
        )

        for expected_hp, expected_remaining in [(90, 2), (80, 1), (70, 0)]:
            logs = BattleService.process_active_effects(combat)
            enemy.refresh_from_db()
            self.assertEqual(enemy.current_hp, expected_hp)
            self.assertEqual(logs[0]['damage'], 10)
            active = ActiveEffect.objects.filter(
                combat_instance=combat, target=enemy, effect_template=ignite
            ).first()
            if expected_remaining:
                self.assertIsNotNone(active)
                self.assertEqual(active.remaining_turns, expected_remaining)
            else:
                self.assertIsNone(active)

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

    def test_entering_normal_dungeon_checks_but_does_not_charge_stamina(self):
        dungeon = NormalDungeonTemplate.objects.create(
            name='Training Ground', stamina_cost=10, required_level=1
        )
        enemy = EnemyTemplate.objects.create(
            name='Entry Slime', level=1, base_hp=10, base_mp=0, base_att=1,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        NormalStageEnemy.objects.create(stage=dungeon, enemy=enemy, count=1)
        stamina_before = self.character.current_stamina

        response = self.client.post(reverse('normal-dungeon-enter', args=[dungeon.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_stamina, stamina_before)
        combat_id = response.data['combat_instance_id']
        battle = CombatInstance.objects.get(pk=combat_id)
        self.assertEqual(battle.stamina_cost_on_victory, 10)
        self.assertFalse(battle.stamina_charged)

    def test_entering_normal_dungeon_still_requires_enough_stamina(self):
        self.character.current_stamina = 9
        self.character.save(update_fields=['current_stamina'])
        dungeon = NormalDungeonTemplate.objects.create(
            name='Costly Training Ground', stamina_cost=10, required_level=1
        )
        enemy = EnemyTemplate.objects.create(
            name='Guard Slime', level=1, base_hp=10, base_mp=0, base_att=1,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        NormalStageEnemy.objects.create(stage=dungeon, enemy=enemy, count=1)

        response = self.client.post(reverse('normal-dungeon-enter', args=[dungeon.pk]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Not enough stamina.')
        self.assertFalse(CombatInstance.objects.exists())

    def test_victory_charges_snapshotted_stamina_once(self):
        dungeon = NormalDungeonTemplate.objects.create(
            name='Training Ground', stamina_cost=10, required_level=1
        )
        combat = self.create_battle(enemy_hp=1)
        combat.normal_dungeon = dungeon
        combat.stamina_cost_on_victory = dungeon.stamina_cost
        combat.save(update_fields=['normal_dungeon', 'stamina_cost_on_victory'])
        target = combat.combatants.get(is_player=False)
        stamina_before = self.character.current_stamina

        # A later admin edit must not alter the cost reserved when the battle began.
        dungeon.stamina_cost = 25
        dungeon.save(update_fields=['stamina_cost'])

        response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.character.refresh_from_db()
        combat.refresh_from_db()
        self.assertEqual(self.character.current_stamina, stamina_before - 10)
        self.assertTrue(combat.stamina_charged)

        BattleService.check_combat_status(combat)
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_stamina, stamina_before - 10)
