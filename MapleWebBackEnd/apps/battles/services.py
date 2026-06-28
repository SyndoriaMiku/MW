from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import CombatInstance, Combatant, ActiveEffect
from apps.party.models import Party
from apps.world.models import EnemyTemplate

class BattleService:
    @staticmethod
    @transaction.atomic
    def create_combat_instance(party: Party, enemies: list[EnemyTemplate]) -> CombatInstance:
        """
        Initializes a new combat instance with the given party and list of enemies.
        """
        combat_instance = CombatInstance.objects.create(party=party)

        # Create Combatants for Party Members
        # Iterate through party members to preserve position
        for party_member in party.party_members.all():
            character = party_member.character
            Combatant.objects.create(
                combat_instance=combat_instance,
                content_type=ContentType.objects.get_for_model(character),
                objects_id=character.id,
                entity=character,
                is_player=True,
                current_hp=character.total_hp,
                current_mp=character.total_mp,
                position=party_member.position 
            )

        # Create Combatants for Enemies
        # Start enemy positions after max party size (e.g., 5)
        enemy_start_position = 5 
        current_index = 0
        
        # Determine if enemies is a list of StageEnemy or EnemyTemplate
        # For backward compatibility or direct calls
        for item in enemies:
            if hasattr(item, 'count'):
                # This is a StageEnemy
                enemy_template = item.enemy
                count = item.count
            else:
                enemy_template = item
                count = 1
                
            for _ in range(count):
                if current_index >= 6:
                    break # MAX 6 ENEMIES TOTAL
                    
                cooldowns = {}
                for es in enemy_template.enemy_skills.all():
                    cooldowns[str(es.skill_template.id)] = es.initial_cd

                Combatant.objects.create(
                    combat_instance=combat_instance,
                    content_type=ContentType.objects.get_for_model(enemy_template),
                    objects_id=enemy_template.id,
                    entity=enemy_template,
                    is_player=False,
                    current_hp=enemy_template.base_hp,
                    current_mp=enemy_template.base_mp,
                    position=enemy_start_position + current_index,
                    skill_cooldowns=cooldowns
                )
                current_index += 1
                
            if current_index >= 6:
                break
        
        return combat_instance

    @staticmethod
    def start_combat(combat_instance: CombatInstance):
        """
        Starts the combat, setting status and initial phase.
        """
        combat_instance.status = CombatInstance.CombatStatus.IN_PROGRESS
        combat_instance.turn_phase = CombatInstance.TURN_PHASE.PLAYER_PHASE
        combat_instance.turn_count = 1
        
        # Set current player to the first available player
        first_player = combat_instance.combatants.filter(is_player=True).order_by('position').first()
        if first_player:
            combat_instance.current_player_position = first_player.position
            
        combat_instance.save()

    @staticmethod
    def end_turn(combat_instance: CombatInstance):
        """
        Ends the current turn. 
        If Player Phase: moves to next player or switches to Monster Phase.
        If Monster Phase: switches to Player Phase (next round).
        """
        if combat_instance.turn_phase == CombatInstance.TURN_PHASE.PLAYER_PHASE:
            # Find next player
            next_player = combat_instance.combatants.filter(
                is_player=True, 
                position__gt=combat_instance.current_player_position,
                current_hp__gt=0
            ).order_by('position').first()

            if next_player:
                combat_instance.current_player_position = next_player.position
            else:
                # No more players this round, switch to Monster Phase
                combat_instance.turn_phase = CombatInstance.TURN_PHASE.MONSTER_PHASE
                # Reset player position for next round (though not used in monster phase)
                first_player = combat_instance.combatants.filter(is_player=True).order_by('position').first()
                if first_player:
                    combat_instance.current_player_position = first_player.position
                
                # Trigger Monster Actions (AI)
                BattleService.process_monster_phase(combat_instance)

        elif combat_instance.turn_phase == CombatInstance.TURN_PHASE.MONSTER_PHASE:
            # Switch back to Player Phase
            combat_instance.turn_phase = CombatInstance.TURN_PHASE.PLAYER_PHASE
            combat_instance.turn_count += 1
            
            # Decrement player cooldowns at the start of a new round
            for p in combat_instance.combatants.filter(is_player=True):
                cooldowns = p.skill_cooldowns
                changed = False
                for skill_id in list(cooldowns.keys()):
                    if cooldowns[skill_id] > 0:
                        cooldowns[skill_id] -= 1
                        changed = True
                if changed:
                    p.skill_cooldowns = cooldowns
                    p.save(update_fields=['skill_cooldowns'])
            
            # Reset to first player
            first_player = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).order_by('position').first()
            if first_player:
                combat_instance.current_player_position = first_player.position
            
            # Process effects at start of round
            BattleService.process_active_effects(combat_instance)
        
        combat_instance.save()

    @staticmethod
    def process_monster_phase(combat_instance: CombatInstance):
        """
        AI logic for monsters.
        """
        import random
        logs = []
        monsters = combat_instance.combatants.filter(is_player=False, current_hp__gt=0).order_by('position')
        players = list(combat_instance.combatants.filter(is_player=True, current_hp__gt=0))

        if not players:
            return logs

        for monster in monsters:
            if not any(p.current_hp > 0 for p in players):
                break

            cooldowns = monster.skill_cooldowns
            for skill_id in list(cooldowns.keys()):
                if cooldowns[skill_id] > 0:
                    cooldowns[skill_id] -= 1
            
            enemy_template = monster.entity
            available_skills = []
            for es in enemy_template.enemy_skills.all():
                skill_id_str = str(es.skill_template.id)
                current_cd = cooldowns.get(skill_id_str, 0)
                if current_cd <= 0 and monster.current_mp >= es.skill_template.mp_cost:
                    available_skills.append(es)
            
            chosen_skill = None
            if available_skills:
                # Sort by priority_index descending
                available_skills.sort(key=lambda x: x.priority_index, reverse=True)
                chosen_skill = available_skills[0].skill_template

            alive_players = [p for p in players if p.current_hp > 0]
            if not alive_players:
                break
            target = random.choice(alive_players)

            if chosen_skill:
                log = BattleService.execute_action(monster, 'SKILL', target, skill_id=chosen_skill.id)
                logs.append(log)
                cooldowns[str(chosen_skill.id)] = chosen_skill.cooldown
            else:
                log = BattleService.execute_action(monster, 'ATTACK', target)
                logs.append(log)

            monster.skill_cooldowns = cooldowns
            monster.save(update_fields=['skill_cooldowns'])

        # End monster phase automatically
        BattleService.end_turn(combat_instance)
        return logs

    @staticmethod
    def apply_damage_with_shield(target, damage: int) -> int:
        """
        Applies damage to a target, reducing it via active shields first.
        Returns the actual damage applied to HP.
        """
        if damage <= 0:
            return 0
        
        # Find active shields
        shields = target.active_effects.filter(remaining_shield_points__gt=0).order_by('created_at')
        actual_hp_damage = damage
        for shield in shields:
            if actual_hp_damage <= 0:
                break
            absorbed = min(shield.remaining_shield_points, actual_hp_damage)
            shield.remaining_shield_points -= absorbed
            actual_hp_damage -= absorbed
            shield.save(update_fields=['remaining_shield_points'])
            
        target.current_hp -= actual_hp_damage
        if target.current_hp < 0:
            target.current_hp = 0
        target.save(update_fields=['current_hp'])
        return actual_hp_damage

    @staticmethod
    def process_active_effects(combat_instance: CombatInstance):
        """
        Process all active effects for the combat instance.
        """
        effects = ActiveEffect.objects.filter(combat_instance=combat_instance)
        for effect in effects:
            # Apply effect logic here (placeholder)
            # e.g., if effect.template.type == 'DOT': apply damage
            
            effect.remaining_turns -= 1
            if effect.remaining_turns <= 0:
                effect.delete()
            else:
                effect.save()

    @staticmethod
    def execute_action(combatant: Combatant, action_type: str, target: Combatant, **kwargs):
        """
        Executes an action (Attack, Skill).
        Returns a dict describing the result of the action (combat log).
        """
        result_log = {
            "actor": str(combatant.entity.name) if hasattr(combatant.entity, 'name') else str(combatant.entity),
            "target": str(target.entity.name) if hasattr(target.entity, 'name') else str(target.entity),
            "action": action_type,
            "damage": 0,
            "heal": 0,
            "is_dead": False,
            "message": ""
        }

        if combatant.current_hp <= 0:
            result_log["message"] = f"{result_log['actor']} tried to act but is dead."
            return result_log
            
        if target.current_hp <= 0:
            result_log["message"] = f"{result_log['target']} is already dead."
            return result_log

        attacker_entity = combatant.entity

        # Reroute Player ATTACK to their Basic Attack SKILL if they have one
        if action_type == 'ATTACK' and combatant.is_player:
            basic_skill = attacker_entity.skills.filter(skill_template__is_basic_attack=True).first()
            if basic_skill:
                action_type = 'SKILL'
                kwargs['skill_id'] = basic_skill.id

        if action_type == 'ATTACK':
            if combatant.is_player:
                # Fallback player attack: uses the robust total_damage calculation
                damage = int(attacker_entity.total_damage)
                skill_name = "Đánh thường"
            else:
                # Monster attack fallback
                damage = int(getattr(attacker_entity, 'base_att', 10))
                skill_name = "Đánh thường"
            
            actual_damage = BattleService.apply_damage_with_shield(target, damage)
            
            result_log["damage"] = actual_damage
            result_log["message"] = f"{result_log['actor']} used {skill_name} and dealt {actual_damage} damage to {result_log['target']}."

        elif action_type == 'SKILL':
            skill_id = kwargs.get('skill_id')
            if not skill_id:
                result_log["message"] = "No skill provided."
                return result_log

            if combatant.is_player:
                from apps.characters.models import CharacterSkill
                try:
                    char_skill = CharacterSkill.objects.get(id=skill_id, character=attacker_entity)
                except CharacterSkill.DoesNotExist:
                    result_log["message"] = "Skill not found for this character."
                    return result_log
                template = char_skill.skill_template
                bonus_final_damage = char_skill.bonus_final_damage
                total_damage = attacker_entity.total_damage
                
                # Check player cooldown
                current_cd = combatant.skill_cooldowns.get(str(template.id), 0)
                if current_cd > 0:
                    result_log["message"] = f"{template.name} is on cooldown for {current_cd} more turns."
                    return result_log
            else:
                from apps.skilles.models import SkillTemplate
                try:
                    template = SkillTemplate.objects.get(id=skill_id)
                except SkillTemplate.DoesNotExist:
                    result_log["message"] = "Skill not found."
                    return result_log
                bonus_final_damage = 0.0
                total_damage = getattr(attacker_entity, 'base_att', 10)

            # Check MP
            if combatant.current_mp < template.mp_cost:
                result_log["message"] = f"Not enough MP to use {template.name}."
                return result_log

            # Consume MP
            combatant.current_mp -= template.mp_cost
            combatant.save(update_fields=['current_mp'])
            
            if combatant.is_player and template.cooldown > 0:
                cooldowns = combatant.skill_cooldowns
                cooldowns[str(template.id)] = template.cooldown
                combatant.skill_cooldowns = cooldowns
                combatant.save(update_fields=['skill_cooldowns'])
            
            result_log["skill_name"] = template.name

            # Calculate Effect
            if template.effect_type == 'DAMAGE':
                base_dmg = (total_damage * template.power_ratio) + template.base_power
                final_skill_dmg = base_dmg * (1 + bonus_final_damage)
                damage = int(final_skill_dmg)
                
                actual_damage = BattleService.apply_damage_with_shield(target, damage)
                
                result_log["damage"] = actual_damage
                result_log["message"] = f"{result_log['actor']} used {template.name} and dealt {actual_damage} damage to {result_log['target']}."

            elif template.effect_type == 'HEAL':
                base_heal = (total_damage * template.power_ratio) + template.base_power
                heal = int(base_heal)
                
                # Assume healing target
                target.current_hp += heal
                # Cap at max HP if possible
                max_hp = getattr(target.entity, 'total_hp', getattr(target.entity, 'base_hp', target.current_hp))
                if target.current_hp > max_hp:
                    target.current_hp = max_hp
                target.save()
                
                result_log["heal"] = heal
                result_log["message"] = f"{result_log['actor']} used {template.name} and healed {result_log['target']} for {heal} HP."

            elif template.effect_type == 'EFFECT':
                result_log["message"] = f"{result_log['actor']} used {template.name} on {result_log['target']}."

            # Apply additional effects if any
            if template.applies_effect:
                ActiveEffect.objects.create(
                    combat_instance=combatant.combat_instance,
                    target=target,
                    effect_template=template.applies_effect,
                    remaining_turns=template.applies_effect.duration_turns,
                    remaining_shield_points=template.applies_effect.shields_points,
                    caster=combatant
                )
                result_log["message"] += f" Applied {template.applies_effect.name}."

        # Check for death
        if target.current_hp <= 0:
            target.current_hp = 0
            target.save()
            result_log["is_dead"] = True
            result_log["message"] += f" {result_log['target']} has been defeated!"
            
        # Check combat status after action
        BattleService.check_combat_status(combatant.combat_instance)
        
        return result_log

    @staticmethod
    def check_combat_status(combat_instance) -> dict:
        """
        Check if the combat has ended (all players dead or all enemies dead).
        Returns a dict with 'status' (ONGOING, VICTORY, DEFEAT) and 'logs' (if any rewards distributed).
        """
        players_alive = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).exists()
        enemies_alive = combat_instance.combatants.filter(is_player=False, current_hp__gt=0).exists()
        
        result = {"status": combat_instance.status, "logs": None}

        if not players_alive:
            combat_instance.status = 'defeat'
            combat_instance.save(update_fields=['status'])
            result["status"] = combat_instance.status
            # Handle death penalty here if needed in the future
        elif not enemies_alive:
            combat_instance.status = 'victory'
            combat_instance.save(update_fields=['status'])
            result["status"] = combat_instance.status
            
            # Process Rewards
            from apps.battles.reward_service import RewardService
            reward_logs = RewardService.process_battle_rewards(combat_instance)
            result["logs"] = reward_logs
            
        return result
