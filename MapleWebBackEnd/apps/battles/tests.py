import uuid
from unittest import mock
from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character, CharacterBuff, CharacterSkill
from apps.classes.models import CharacterClass, Job
from apps.inventory.models import InventoryItem
from apps.items.models import BattleConsumableRule, ItemTemplate
from apps.market.models import Listing
from apps.party.models import Party, PartyMember, PendingPartyLoot
from apps.users.models import GameUser
from apps.world.models import (
    EnemySkill, EnemyTemplate, LootTable, NormalDungeonTemplate, NormalStageEnemy,
)
from apps.skilles.models import EffectTemplate, SkillLevelConfig, SkillTemplate, SpecialEffectTag

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


class BattleFixtureMixin:
    """A solo party (self.party) for self.character/self.user, plus battle helpers."""

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


class NormalAttackSceneContractTests(BattleFixtureMixin, APITestCase):
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

    def give_buff(self, **bonuses):
        now = timezone.now()
        CharacterBuff.objects.create(
            character=self.character,
            source_template=ItemTemplate.objects.create(name='Charm', item_type='use'),
            started_at=now, expires_at=now + timedelta(minutes=30), **bonuses,
        )

    def test_epic_drop_buff_boosts_only_epic_loot(self):
        combat = self.create_battle(enemy_hp=1)
        target = combat.combatants.get(is_player=False)
        for drop_type in ('common', 'epic', 'legendary'):
            LootTable.objects.create(
                enemy=target.entity,
                item_template=ItemTemplate.objects.create(name=f'{drop_type} drop', item_type='etc'),
                base_drop_rate=0.5, drop_type=drop_type,
            )
        self.give_buff(epic_drop_rate_bonus=100)

        with mock.patch('apps.battles.reward_service.random.random', return_value=0.6):
            self.act(combat, target)

        owned = set(
            InventoryItem.objects.filter(owner=self.character).values_list('template__name', flat=True)
        )
        self.assertEqual(owned, {'epic drop'})

    def test_exp_and_lumis_buffs_scale_battle_rewards(self):
        combat = self.create_battle(enemy_hp=1)
        target = combat.combatants.get(is_player=False)
        EnemyTemplate.objects.filter(pk=target.objects_id).update(
            exp_reward=10, lumis_reward_min=10, lumis_reward_max=10,
        )
        self.give_buff(exp_rate_bonus=100, lumis_rate_bonus=50)

        self.act(combat, target)

        self.character.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.character.current_exp, 20)
        self.assertEqual(self.user.lumis, 15)

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


class SoloSharedLootTests(APITestCase):
    def test_shared_loot_goes_straight_to_a_solo_player(self):
        character = Character.objects.create(name='Solo Looter')
        user = GameUser.objects.create_user(
            username='solo-looter', email='solo-looter@example.com', password='test-pass-123'
        )
        user.character = character
        user.save(update_fields=['character'])
        party = Party.objects.create(name='Solo', leader=character, max_size=1, is_solo=True)
        PartyMember.objects.create(party=party, character=character, position=1)
        enemy = EnemyTemplate.objects.create(
            name='Shared Slime', level=1, base_hp=1, base_mp=0, base_att=0,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        gem = ItemTemplate.objects.create(name='Shared Gem', item_type='etc')
        LootTable.objects.create(
            enemy=enemy, item_template=gem, base_drop_rate=1, is_party_shared=True,
        )
        combat = BattleService.create_combat_instance(party, [enemy])
        BattleService.start_combat(combat)
        self.client.force_authenticate(user)

        self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': combat.combatants.get(is_player=False).id},
            format='json',
        )

        self.assertTrue(InventoryItem.objects.filter(owner=character, template=gem).exists())
        self.assertFalse(PendingPartyLoot.objects.exists())


class BattleConsumableTests(BattleFixtureMixin, APITestCase):
    """Potions: using one takes the player's whole turn."""

    def setUp(self):
        super().setUp()
        self.potion_template = ItemTemplate.objects.create(name='Red Potion', item_type='use')
        self.rule = BattleConsumableRule.objects.create(
            item_template=self.potion_template, hp_restore=20,
        )
        self.potion = InventoryItem.objects.create(
            owner=self.character, template=self.potion_template, quantity=3
        )

    def use(self, combat, target=None, item=None):
        data = {'action_type': 'ITEM', 'inventory_item_id': (item or self.potion).id}
        if target is not None:
            data['target_id'] = target.id
        return self.client.post(
            reverse('battles:player-action', args=[combat.id]), data, format='json'
        )

    def wounded_battle(self, hp=10):
        combat = self.create_battle(enemy_hp=500, enemy_attack=0)
        player = combat.combatants.get(is_player=True, position=1)
        player.current_hp = hp
        player.save(update_fields=['current_hp'])
        return combat, player

    def test_potion_heals_consumes_one_and_ends_the_turn(self):
        combat, player = self.wounded_battle()

        response = self.use(combat)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = response.data['action_log']
        self.assertTrue(log['success'])
        self.assertEqual((log['action'], log['heal']), ('ITEM', 20))
        player.refresh_from_db()
        self.potion.refresh_from_db()
        self.assertEqual((player.current_hp, self.potion.quantity), (30, 2))
        self.assertEqual(response.data['combat']['turn_count'], 2)

    def test_percent_restore_is_capped_at_max_hp(self):
        self.rule.hp_restore = 0
        self.rule.hp_restore_percent = 1.0
        self.rule.save()
        combat, player = self.wounded_battle()

        self.use(combat)

        player.refresh_from_db()
        self.assertEqual(player.current_hp, self.character.total_hp)

    def test_ally_potion_heals_a_teammate_but_self_potion_does_not(self):
        _, ally_character = self.add_party_member('potion-ally')
        combat, _ = self.wounded_battle()
        ally = combat.combatants.get(is_player=True, position=2)
        ally.current_hp = 5
        ally.save(update_fields=['current_hp'])
        enemy = combat.combatants.get(is_player=False)

        self_only = self.use(combat, target=ally)
        self.rule.target_type = 'ALLY'
        self.rule.save()
        at_enemy = self.use(combat, target=enemy)
        healed = self.use(combat, target=ally)

        self.assertFalse(self_only.data['action_log']['success'])
        self.assertFalse(at_enemy.data['action_log']['success'])
        self.assertTrue(healed.data['action_log']['success'])
        ally.refresh_from_db()
        self.assertEqual(ally.current_hp, 25)

    def test_cooldown_blocks_reuse_without_consuming(self):
        self.rule.cooldown_turns = 2
        self.rule.save()
        combat, _ = self.wounded_battle()

        self.use(combat)
        second = self.use(combat)

        self.assertFalse(second.data['action_log']['success'])
        self.potion.refresh_from_db()
        self.assertEqual(self.potion.quantity, 2)

    def test_items_without_a_rule_or_reserved_cannot_be_used(self):
        combat, _ = self.wounded_battle()
        junk = InventoryItem.objects.create(
            owner=self.character, template=ItemTemplate.objects.create(name='Junk', item_type='etc')
        )
        Listing.objects.create(seller=self.user, item=self.potion, price=1, quantity=1)

        for item in (junk, self.potion):
            with self.subTest(item=item.template.name):
                self.assertFalse(self.use(combat, item=item).data['action_log']['success'])

    def test_snapshot_lists_usable_consumables(self):
        combat, player = self.wounded_battle()

        snapshot = self.client.get(reverse('battles:battle-state', args=[combat.id])).data
        me = next(c for c in snapshot['combatants'] if c['id'] == player.id)

        self.assertIn('ITEM', me['valid_actions'])
        self.assertEqual(len(me['consumables']), 1)
        entry = me['consumables'][0]
        self.assertEqual(
            (entry['inventory_item_id'], entry['quantity'], entry['can_use']),
            (self.potion.id, 3, True),
        )

    def test_item_action_requires_an_inventory_item(self):
        serializer = PlayerActionSerializer(data={'action_type': 'ITEM'})

        self.assertFalse(serializer.is_valid())
        self.assertIn('inventory_item_id', serializer.errors)


class FallenPlayerRewardTests(BattleFixtureMixin, APITestCase):
    """Players who die still share the victory; players who forfeit leave with nothing."""

    def setUp(self):
        super().setUp()
        self.ally_user, self.ally = self.add_party_member('fallen-ally')
        self.combat = self.create_battle(enemy_hp=1)
        self.enemy = self.combat.combatants.get(is_player=False)
        EnemyTemplate.objects.filter(pk=self.enemy.objects_id).update(exp_reward=10)
        LootTable.objects.create(
            enemy_id=self.enemy.objects_id, base_drop_rate=1,
            item_template=ItemTemplate.objects.create(name='Trophy', item_type='etc'),
        )
        self.ally_combatant = self.combat.combatants.get(is_player=True, position=2)

    def win(self):
        self.client.force_authenticate(self.user)
        return self.client.post(
            reverse('battles:player-action', args=[self.combat.id]),
            {'action_type': 'ATTACK', 'target_id': self.enemy.id}, format='json',
        )

    def forfeit_as_ally(self):
        self.client.force_authenticate(self.ally_user)
        return self.client.post(reverse('battles:forfeit', args=[self.combat.id]))

    def trophies(self, character):
        return InventoryItem.objects.filter(owner=character, template__name='Trophy').count()

    def test_player_dead_at_victory_shares_the_rewards(self):
        self.ally_combatant.current_hp = 0
        self.ally_combatant.save(update_fields=['current_hp'])

        response = self.win()

        self.assertEqual(response.data['combat']['status'], 'victory')
        self.ally.refresh_from_db()
        self.character.refresh_from_db()
        self.assertEqual((self.ally.current_exp, self.character.current_exp), (5, 5))
        self.assertEqual((self.trophies(self.ally), self.trophies(self.character)), (1, 1))

    def test_dead_player_only_watches(self):
        self.ally_combatant.current_hp = 0
        self.ally_combatant.save(update_fields=['current_hp'])
        self.client.force_authenticate(self.ally_user)

        watched = self.client.get(reverse('battles:battle-state', args=[self.combat.id]))
        acted = self.client.post(
            reverse('battles:player-action', args=[self.combat.id]),
            {'action_type': 'ATTACK', 'target_id': self.enemy.id}, format='json',
        )

        self.assertEqual(watched.status_code, status.HTTP_200_OK)
        self.assertEqual(acted.status_code, status.HTTP_400_BAD_REQUEST)

    def test_forfeited_player_gets_nothing(self):
        self.assertEqual(self.forfeit_as_ally().status_code, status.HTTP_200_OK)

        self.win()

        self.ally.refresh_from_db()
        self.character.refresh_from_db()
        self.assertEqual((self.ally.current_exp, self.character.current_exp), (0, 10))
        self.assertEqual(self.trophies(self.ally), 0)

    def test_dead_player_may_still_forfeit_and_give_up_the_rewards(self):
        self.ally_combatant.current_hp = 0
        self.ally_combatant.save(update_fields=['current_hp'])

        self.assertEqual(self.forfeit_as_ally().status_code, status.HTTP_200_OK)
        self.assertEqual(self.forfeit_as_ally().status_code, status.HTTP_400_BAD_REQUEST)

        self.win()
        self.ally.refresh_from_db()
        self.assertEqual(self.ally.current_exp, 0)

    def test_forfeited_player_is_free_to_do_other_things(self):
        from apps.inventory.reservations import character_in_active_battle

        self.forfeit_as_ally()

        self.assertIsNone(BattleService.get_active_combat_for_character(self.ally))
        self.assertFalse(character_in_active_battle(self.ally))
        self.assertIsNotNone(BattleService.get_active_combat_for_character(self.character))

    def test_boss_clear_is_logged_for_dead_members_too(self):
        from apps.world.models import BossDungeonTemplate, DungeonClearLog

        boss = BossDungeonTemplate.objects.create(name='Fallen Boss')
        CombatInstance.objects.filter(pk=self.combat.pk).update(boss_dungeon=boss)
        self.ally_combatant.current_hp = 0
        self.ally_combatant.save(update_fields=['current_hp'])

        self.win()

        self.assertEqual(
            set(DungeonClearLog.objects.filter(dungeon=boss).values_list('character_id', flat=True)),
            {self.character.pk, self.ally.pk},
        )


class CombatEffectMechanicsTests(BattleFixtureMixin, APITestCase):
    """Effect durations, stun/silence, max HP/MP, restore modifiers, cooldown reduction and dispels."""

    def effect(self, name='Effect', *, tags=(), **fields):
        fields.setdefault('duration_turns', 1)
        effect = EffectTemplate.objects.create(name=name, **fields)
        for tag in tags:
            effect.special_effects.add(
                SpecialEffectTag.objects.get_or_create(id=tag, defaults={'name': tag})[0]
            )
        return effect

    def put(self, target, effect, turns=3):
        return ActiveEffect.objects.create(
            combat_instance=target.combat_instance, target=target,
            effect_template=effect, remaining_turns=turns,
        )

    def enemy_with_skill(self, skill, *, attack=0):
        enemy = EnemyTemplate.objects.create(
            name='Caster', level=1, base_hp=500, base_mp=0, base_att=attack,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        EnemySkill.objects.create(enemy_template=enemy, skill_template=skill, priority_index=1)
        combat = BattleService.create_combat_instance(self.party, [enemy])
        BattleService.start_combat(combat)
        return combat

    def owned_skill(self, **fields):
        skill = SkillTemplate.objects.create(**fields)
        return CharacterSkill.objects.create(character=self.character, skill_template=skill, level=1)

    def act(self, combat, action_type='ATTACK', **data):
        if action_type == 'ATTACK':
            data.setdefault('target_id', combat.combatants.get(is_player=False).id)
        return self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': action_type, **data}, format='json',
        )

    @staticmethod
    def skips(response):
        return [
            (event['actor_type'], event['reason'])
            for event in response.data['events'] if event.get('event_type') == 'turn_skipped'
        ]

    def test_monster_stun_costs_the_player_exactly_one_turn(self):
        stun = self.effect('Stun', effect_kind='DEBUFF', tags=['stun'])
        bash = SkillTemplate.objects.create(
            name='Bash', availability='ENEMY', target_type='ENEMY',
            effect_type='EFFECT', applies_effect=stun, cooldown=5,
        )
        combat = self.enemy_with_skill(bash)

        response = self.act(combat)

        self.assertEqual(self.skips(response), [('character', 'stunned')])
        self.assertEqual(response.data['combat']['turn_phase'], 'player_phase')
        self.assertEqual(response.data['combat']['turn_count'], 3)
        self.assertFalse(ActiveEffect.objects.filter(effect_template=stun).exists())

    def test_player_stun_skips_only_the_enemys_next_phase(self):
        stun = self.effect('Stun', effect_kind='DEBUFF', tags=['stun'])
        owned = self.owned_skill(
            name='Stun Shot', target_type='ENEMY', effect_type='EFFECT', applies_effect=stun,
        )
        combat = self.create_battle(enemy_hp=500, enemy_attack=7)
        player = combat.combatants.get(is_player=True)
        hp_before = player.current_hp
        enemy = combat.combatants.get(is_player=False)

        stunned = self.act(combat, 'SKILL', character_skill_id=owned.id, target_id=enemy.id)
        player.refresh_from_db()

        self.assertEqual(self.skips(stunned), [('enemy', 'stunned')])
        self.assertEqual(player.current_hp, hp_before)
        self.assertFalse(ActiveEffect.objects.filter(effect_template=stun).exists())

        recovered = self.act(combat)
        player.refresh_from_db()

        self.assertEqual(self.skips(recovered), [])
        self.assertEqual(player.current_hp, hp_before - 7)

    def test_self_buff_covers_the_casters_next_turn(self):
        rage = self.effect('Rage', flat_att_change=10)
        owned = self.owned_skill(
            name='Rage', target_type='SELF', effect_type='EFFECT', applies_effect=rage,
        )
        combat = self.create_battle(enemy_hp=500)

        self.act(combat, 'SKILL', character_skill_id=owned.id)

        self.assertEqual(ActiveEffect.objects.get(effect_template=rage).remaining_turns, 1)
        buffed = self.act(combat)
        # No job: damage is the ATT total, 5 base + 10 from the buff.
        self.assertEqual(buffed.data['action_log']['damage'], 15)
        self.assertFalse(ActiveEffect.objects.filter(effect_template=rage).exists())

    def test_silence_blocks_skills_but_not_basic_attacks(self):
        owned = self.owned_skill(name='Fireball', target_type='ENEMY', effect_type='DAMAGE', base_power=5)
        combat = self.create_battle(enemy_hp=500)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        self.put(player, self.effect('Silence', effect_kind='DEBUFF', tags=['silence'], duration_turns=3))

        snapshot = self.client.get(reverse('battles:battle-state', args=[combat.id])).data
        me = next(c for c in snapshot['combatants'] if c['id'] == player.id)
        fireball = next(s for s in me['skills'] if s['character_skill_id'] == owned.id)
        self.assertFalse(fireball['can_use'])
        self.assertEqual(me['active_effects'][0]['special_effects'], ['silence'])

        self.assertFalse(
            BattleService.execute_action(player, 'SKILL', enemy, character_skill_id=owned.id)['success']
        )
        self.assertTrue(BattleService.execute_action(player, 'ATTACK', enemy)['success'])

    def test_silenced_monster_falls_back_to_a_basic_attack(self):
        blast = SkillTemplate.objects.create(
            name='Blast', availability='ENEMY', target_type='ENEMY', effect_type='DAMAGE', base_power=50,
        )
        combat = self.enemy_with_skill(blast, attack=3)
        self.put(combat.combatants.get(is_player=False), self.effect('Silence', tags=['silence']))

        response = self.act(combat)

        monster_action = response.data['events'][1]
        self.assertEqual((monster_action['action'], monster_action['damage']), ('ATTACK', 3))

    def test_max_hp_buff_raises_the_cap_and_hp_is_clamped_when_it_ends(self):
        combat = self.create_battle()
        player = combat.combatants.get(is_player=True)
        base = self.character.total_hp
        self.put(player, self.effect('Fortify', flat_hp_change=50), turns=1)
        player.current_hp = base + 50
        player.save(update_fields=['current_hp'])

        snapshot = self.client.get(reverse('battles:battle-state', args=[combat.id])).data
        self.assertEqual(next(c for c in snapshot['combatants'] if c['id'] == player.id)['max_hp'], base + 50)

        BattleService.process_active_effects(combat, players=True)

        player.refresh_from_db()
        self.assertEqual(player.current_hp, base)

    def test_mana_received_modifier_scales_potions(self):
        self.character.base_mp = 100
        self.character.save(update_fields=['base_mp'])
        combat = self.create_battle()
        player = combat.combatants.get(is_player=True)
        player.current_mp = 0
        player.save(update_fields=['current_mp'])
        self.put(player, self.effect('Clarity', mana_received_modifier=1.0))
        ether = ItemTemplate.objects.create(name='Ether', item_type='use')
        BattleConsumableRule.objects.create(item_template=ether, mp_restore=10)
        stack = InventoryItem.objects.create(owner=self.character, template=ether, quantity=1)

        log = BattleService.execute_action(player, 'ITEM', None, inventory_item_id=stack.id)

        self.assertEqual(log['mp_restored'], 20)

    def test_healing_over_time_uses_healing_modifiers(self):
        combat = self.create_battle()
        player = combat.combatants.get(is_player=True)
        player.current_hp = 1
        player.save(update_fields=['current_hp'])
        self.put(player, self.effect('Regen', hp_change_per_turn=10))
        self.put(player, self.effect('Blessed', health_received_modifier=0.5))

        BattleService.process_active_effects(combat, players=True)

        player.refresh_from_db()
        self.assertEqual(player.current_hp, 16)

    def test_cooldown_reduction_shortens_new_skill_cooldowns(self):
        owned = self.owned_skill(name='Big Hit', target_type='ENEMY', effect_type='DAMAGE', cooldown=3)
        combat = self.create_battle(enemy_hp=500)
        player = combat.combatants.get(is_player=True)
        self.put(player, self.effect('Haste', cooldown_reduction=2))

        BattleService.execute_action(
            player, 'SKILL', combat.combatants.get(is_player=False), character_skill_id=owned.id,
        )

        player.refresh_from_db()
        self.assertEqual(player.skill_cooldowns[str(owned.skill_template_id)], 1)

    def test_dispel_removes_dispellable_ally_debuffs_and_enemy_buffs(self):
        combat = self.create_battle(enemy_hp=500)
        player = combat.combatants.get(is_player=True)
        enemy = combat.combatants.get(is_player=False)
        poison = self.effect('Poison', effect_kind='DEBUFF')
        curse = self.effect('Curse', effect_kind='DEBUFF', dispellable=False)
        guard = self.effect('Guard', effect_kind='BUFF')
        enrage = self.effect('Enrage', effect_kind='BUFF')
        for target, effect in ((player, poison), (player, curse), (player, guard), (enemy, enrage)):
            self.put(target, effect)
        cleanse = self.effect('Cleanse', dispel_count=5, duration_turns=0)
        purge = self.effect('Purge', dispel_count=1, duration_turns=0)

        BattleService._apply_skill_effect(player, player, cleanse)
        BattleService._apply_skill_effect(player, enemy, purge)

        remaining = set(ActiveEffect.objects.values_list('effect_template__name', flat=True))
        self.assertEqual(remaining, {'Curse', 'Guard'})
