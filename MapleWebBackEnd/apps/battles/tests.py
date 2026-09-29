import uuid
from unittest import mock
from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character, CharacterSkill
from apps.classes.models import CharacterClass, Job
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.party.models import Party, PartyMember
from apps.users.models import GameUser
from apps.world.models import (
    EnemySkill, EnemyTemplate, LootTable, NormalDungeonTemplate, NormalStageEnemy,
)
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

    def act(self, combat, target, **extra):
        return self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id, **extra},
            format='json',
        )

    def test_snapshot_exposes_a_version_that_each_action_increments(self):
        combat = self.create_battle(enemy_hp=100)
        target = combat.combatants.get(is_player=False)
        before = self.client.get(reverse('battles:battle-state', args=[combat.id]))

        response = self.act(combat, target)

        self.assertEqual(before.data['version'], 0)
        self.assertEqual(response.data['combat']['version'], 1)

    def test_retrying_a_client_action_id_replays_instead_of_acting_again(self):
        combat = self.create_battle(enemy_hp=100)
        target = combat.combatants.get(is_player=False)
        action_id = str(uuid.uuid4())

        first = self.act(combat, target, client_action_id=action_id)
        target.refresh_from_db()
        hp_after_first = target.current_hp
        retry = self.act(combat, target, client_action_id=action_id)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertFalse(first.data['replayed'])
        self.assertTrue(retry.data['replayed'])
        self.assertEqual(retry.data['events'], first.data['events'])
        target.refresh_from_db()
        self.assertEqual(target.current_hp, hp_after_first)
        combat.refresh_from_db()
        self.assertEqual(combat.version, 1)

    def test_retrying_the_finishing_action_does_not_grant_rewards_twice(self):
        combat = self.create_battle(enemy_hp=1)
        EnemyTemplate.objects.filter(pk=combat.combatants.get(is_player=False).objects_id).update(
            lumis_reward_min=10, lumis_reward_max=10,
        )
        target = combat.combatants.get(is_player=False)
        action_id = str(uuid.uuid4())

        first = self.act(combat, target, client_action_id=action_id)
        retry = self.act(combat, target, client_action_id=action_id)

        self.assertEqual(first.data['combat']['status'], 'victory')
        self.assertTrue(retry.data['replayed'])
        self.assertEqual(retry.data['combat']['status'], 'victory')
        self.user.refresh_from_db()
        self.assertEqual(self.user.lumis, 10)

    def test_stale_expected_version_is_rejected_with_current_snapshot(self):
        combat = self.create_battle(enemy_hp=100)
        target = combat.combatants.get(is_player=False)
        self.act(combat, target, expected_version=0)
        target.refresh_from_db()
        hp_before = target.current_hp

        stale = self.act(combat, target, expected_version=0)

        self.assertEqual(stale.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(stale.data['combat']['version'], 1)
        target.refresh_from_db()
        self.assertEqual(target.current_hp, hp_before)

    def test_client_action_id_must_be_a_uuid(self):
        combat = self.create_battle(enemy_hp=100)
        target = combat.combatants.get(is_player=False)

        response = self.act(combat, target, client_action_id='not-a-uuid')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_drop_rate_bonus_only_boosts_common_loot(self):
        combat = self.create_battle(enemy_hp=1)
        target = combat.combatants.get(is_player=False)
        templates = {}
        for drop_type in ('common', 'epic', 'legendary'):
            templates[drop_type] = ItemTemplate.objects.create(
                name=f'{drop_type} drop', item_type='etc'
            )
            LootTable.objects.create(
                enemy=target.entity, item_template=templates[drop_type],
                base_drop_rate=0.5, drop_type=drop_type,
            )

        # A roll of 0.6 only succeeds when the 0.5 base rate is doubled.
        with mock.patch('apps.battles.reward_service.random.random', return_value=0.6), \
                mock.patch.object(Character, 'total_drop_rate', new_callable=mock.PropertyMock, return_value=2.0):
            self.act(combat, target)

        owned = set(
            InventoryItem.objects.filter(owner=self.character).values_list('template__name', flat=True)
        )
        self.assertEqual(owned, {'common drop'})

    def test_victory_loot_merges_when_character_owns_several_stacks(self):
        combat = self.create_battle(enemy_hp=1)
        target = combat.combatants.get(is_player=False)
        potion = ItemTemplate.objects.create(name='Loot Potion', item_type='use')
        LootTable.objects.create(
            enemy=target.entity, item_template=potion,
            base_drop_rate=1, min_quantity=2, max_quantity=2,
        )
        oldest = InventoryItem.objects.create(owner=self.character, template=potion, quantity=3)
        InventoryItem.objects.create(owner=self.character, template=potion, quantity=4)

        response = self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['combat']['status'], 'victory')
        oldest.refresh_from_db()
        self.assertEqual(oldest.quantity, 5)
        self.assertEqual(
            InventoryItem.objects.filter(owner=self.character, template=potion).count(), 2
        )

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

    def create_enemy(self, name, *, hp=100, attack=0, skill=None):
        enemy = EnemyTemplate.objects.create(
            name=name, level=1, base_hp=hp, base_mp=0, base_att=attack,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        if skill:
            EnemySkill.objects.create(enemy_template=enemy, skill_template=skill, priority_index=1)
        return enemy

    def run_monster_phase(self, enemies):
        combat = BattleService.create_combat_instance(self.party, enemies)
        BattleService.start_combat(combat)
        combat.turn_phase = CombatInstance.TURN_PHASE.MONSTER_PHASE
        combat.save(update_fields=['turn_phase'])
        return combat, BattleService.process_monster_phase(combat)

    def test_monster_area_damage_is_kept_when_a_later_monster_attacks(self):
        quake = SkillTemplate.objects.create(
            name='Quake', availability='ENEMY', target_type='E_AREA',
            effect_type='DAMAGE', base_power=5, power_ratio=0,
        )
        caster = self.create_enemy('Quake Caster', skill=quake)
        brute = self.create_enemy('Brute', attack=3)

        combat, _ = self.run_monster_phase([caster, brute])

        player = combat.combatants.get(is_player=True)
        self.assertEqual(player.current_hp, self.character.total_hp - 5 - 3)

    def test_monster_killed_earlier_in_the_phase_does_not_act(self):
        blast = SkillTemplate.objects.create(
            name='Blast', availability='ENEMY', target_type='GLOBAL',
            effect_type='DAMAGE', base_power=10, power_ratio=0,
        )
        bomber = self.create_enemy('Bomber', skill=blast)
        weakling = self.create_enemy('Weakling', hp=5, attack=7)

        combat, logs = self.run_monster_phase([bomber, weakling])

        player = combat.combatants.get(is_player=True)
        self.assertEqual(player.current_hp, self.character.total_hp - 10)
        self.assertEqual([log['actor'] for log in logs], ['Bomber'])

    def test_every_periodic_effect_on_the_same_target_is_applied(self):
        poison = EffectTemplate.objects.create(
            name='Poison', duration_turns=2, hp_change_per_turn=-5,
            stacking_rule='INDEPENDENT',
        )
        combat = self.create_multi_enemy_battle(count=1, enemy_hp=100)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        for _ in range(2):
            ActiveEffect.objects.create(
                combat_instance=combat, target=enemy, effect_template=poison,
                remaining_turns=2, caster=player,
            )

        BattleService.process_active_effects(combat)

        enemy.refresh_from_db()
        self.assertEqual(enemy.current_hp, 90)

    def make_strength_fighter(self):
        """STR class/job with 10 STR and 100 ATT: base damage 10*100/100 = 10."""
        warrior = CharacterClass.objects.create(name='Warrior', main_stat='str')
        self.character.character_class = warrior
        self.character.job = Job.objects.create(name='Fighter', character_class=warrior)
        self.character.base_str = 10
        self.character.base_att = 100
        self.character.save()

    def buff(self, combatant, **changes):
        effect = EffectTemplate.objects.create(name='Buff', duration_turns=3, **changes)
        ActiveEffect.objects.create(
            combat_instance=combatant.combat_instance, target=combatant,
            effect_template=effect, remaining_turns=3,
        )

    def test_main_stat_buff_raises_player_attack_damage(self):
        self.make_strength_fighter()
        combat = self.create_battle(enemy_hp=500)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        self.buff(player, flat_str_change=10)

        log = BattleService.execute_action(player, 'ATTACK', enemy)

        self.assertEqual(log['damage'], 20)

    def test_att_buff_scales_through_the_damage_formula_for_skills(self):
        self.make_strength_fighter()
        _, owned = self.create_owned_skill(
            name='Slash', target_type='ENEMY', base_power=0, power_ratio=1,
        )
        combat = self.create_battle(enemy_hp=500)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        self.buff(player, flat_att_change=100)

        log = BattleService.execute_action(
            player, 'SKILL', enemy, character_skill_id=owned.id
        )

        self.assertEqual(log['damage'], 20)

    def test_att_buff_raises_enemy_basic_attack(self):
        combat = self.create_battle(enemy_attack=10)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        self.buff(enemy, percent_att_change=0.5)

        log = BattleService.execute_action(enemy, 'ATTACK', player)

        self.assertEqual(log['damage'], 15)

    def apply_effect(self, target, *, turns=3, **changes):
        effect = EffectTemplate.objects.create(name='Tick', duration_turns=turns, **changes)
        return ActiveEffect.objects.create(
            combat_instance=target.combat_instance, target=target,
            effect_template=effect, remaining_turns=turns,
            remaining_shield_points=changes.get('shields_points', 0),
        )

    def test_periodic_effect_ticks_are_returned_as_events(self):
        combat = self.create_battle(enemy_hp=500, enemy_attack=0)
        enemy = combat.combatants.get(is_player=False)
        self.apply_effect(enemy, turns=1, hp_change_per_turn=-5)

        response = self.act(combat, enemy)

        ticks = [e for e in response.data['events'] if e.get('event_type') == 'effect_tick']
        self.assertEqual(len(ticks), 1)
        self.assertEqual(ticks[0]['target_id'], enemy.id)
        self.assertEqual(ticks[0]['hp_change'], -5)
        self.assertTrue(ticks[0]['expired'])
        self.assertEqual(response.data['events'][0]['event_type'], 'action')

    def test_victory_by_periodic_damage_reports_the_battle_result(self):
        combat = self.create_battle(enemy_hp=8, enemy_attack=0)
        enemy = combat.combatants.get(is_player=False)
        self.apply_effect(enemy, hp_change_per_turn=-5)

        response = self.act(combat, enemy)

        self.assertEqual(response.data['combat']['status'], 'victory')
        final = response.data['events'][-1]
        self.assertEqual(final['event_type'], 'effect_tick')
        self.assertTrue(final['is_dead'])
        self.assertEqual(final['battle_result']['status'], 'victory')

    def test_shield_absorption_is_reported_per_target(self):
        combat = self.create_battle(enemy_hp=500)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        self.apply_effect(enemy, shields_points=3)

        log = BattleService.execute_action(player, 'ATTACK', enemy)

        self.assertEqual(log['targets'][0]['shield_absorbed'], 3)
        self.assertEqual(log['damage'], self.character.total_damage - 3)

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

    def add_party_member(self, name):
        """Second player at position 2; returns (user, character)."""
        self.party.max_size = 2
        self.party.save(update_fields=['max_size'])
        character = Character.objects.create(name=name)
        user = GameUser.objects.create_user(
            username=name, email=f'{name}@example.com', password='test-pass-123'
        )
        user.character = character
        user.save(update_fields=['character'])
        PartyMember.objects.create(party=self.party, character=character, position=2)
        return user, character

    def test_forfeit_ends_a_solo_battle_as_defeat(self):
        combat = self.create_battle(enemy_hp=500)

        response = self.client.post(reverse('battles:forfeit', args=[combat.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['combat']['status'], 'defeat')
        self.assertEqual(response.data['combat']['version'], 1)
        self.assertIsNone(BattleService.get_active_combat_for_character(self.character))

    def test_forfeit_rejects_outsiders_and_finished_battles(self):
        combat = self.create_battle(enemy_hp=500)
        outsider = GameUser.objects.create_user(
            username='forfeit-outsider', email='fo@example.com', password='test-pass-123'
        )
        outsider.character = Character.objects.create(name='Outsider')
        outsider.save(update_fields=['character'])
        url = reverse('battles:forfeit', args=[combat.id])

        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.post(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.user)
        self.client.post(url)
        self.assertEqual(self.client.post(url).status_code, status.HTTP_400_BAD_REQUEST)

    def test_current_actor_forfeiting_passes_the_turn_on(self):
        _, ally = self.add_party_member('forfeit-ally')
        combat = self.create_battle(enemy_hp=500)

        response = self.client.post(reverse('battles:forfeit', args=[combat.id]))

        self.assertEqual(response.data['combat']['status'], 'in_progress')
        self.assertEqual(response.data['combat']['current_player_position'], 2)

    @override_settings(BATTLE_TURN_TIMEOUT_SECONDS=60)
    def test_idle_turn_can_be_skipped_only_after_the_timeout(self):
        ally_user, _ = self.add_party_member('idle-ally')
        combat = self.create_battle(enemy_hp=500)
        url = reverse('battles:skip-idle-turn', args=[combat.id])
        self.client.force_authenticate(ally_user)

        too_early = self.client.post(url)
        CombatInstance.objects.filter(pk=combat.pk).update(
            turn_started_at=timezone.now() - timedelta(seconds=61)
        )
        skipped = self.client.post(url)

        self.assertEqual(too_early.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(skipped.status_code, status.HTTP_200_OK)
        self.assertEqual(skipped.data['combat']['current_player_position'], 2)
        self.assertEqual(skipped.data['combat']['version'], 1)

    def test_turn_start_time_moves_with_the_turn(self):
        combat = self.create_battle(enemy_hp=500)
        started = combat.turn_started_at
        CombatInstance.objects.filter(pk=combat.pk).update(
            turn_started_at=timezone.now() - timedelta(hours=1)
        )

        self.act(combat, combat.combatants.get(is_player=False))

        combat.refresh_from_db()
        self.assertIsNotNone(started)
        self.assertGreater(combat.turn_started_at, timezone.now() - timedelta(minutes=1))

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
