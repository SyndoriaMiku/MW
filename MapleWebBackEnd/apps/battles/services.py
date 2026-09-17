from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import CombatInstance, Combatant, ActiveEffect
from apps.party.models import Party
from apps.world.models import EnemyTemplate
from collections import defaultdict


def _prefetch_entities(combatants):
    """
    (M4/M5 fix) Batch-resolve GenericForeignKey `.entity` for a list of combatants.
    Groups combatants by content_type, does ONE query per type, then caches on each instance.
    Eliminates N+1 queries when accessing combatant.entity.
    """
    # Group by content_type
    ct_groups = defaultdict(list)
    for c in combatants:
        ct_groups[c.content_type_id].append(c)
    
    for ct_id, group in ct_groups.items():
        ct = ContentType.objects.get_for_id(ct_id)
        model_class = ct.model_class()
        ids = [c.objects_id for c in group]
        
        # Single query for all objects of this type
        objects = {str(obj.pk): obj for obj in model_class.objects.filter(pk__in=ids)}
        
        # Cache on each combatant's GenericFK
        for c in group:
            c._entity_cache = objects.get(c.objects_id)

class BattleService:
    @staticmethod
    def get_active_combat_for_character(character):
        """Return the persisted in-progress combat that contains this character."""
        character_type = ContentType.objects.get_for_model(character)
        return CombatInstance.objects.filter(
            combatants__is_player=True,
            combatants__content_type=character_type,
            combatants__objects_id=str(character.pk),
            status=CombatInstance.CombatStatus.IN_PROGRESS,
        ).select_related('normal_dungeon', 'boss_dungeon').order_by('-updated_at').first()

    @staticmethod
    def _is_valid_skill_target(actor: Combatant, target: Combatant, target_type: str) -> bool:
        """Enforce target-side rules before an action consumes MP or cooldown."""
        if target is None:
            return target_type in ('SELF', 'E_AREA', 'A_AREA', 'GLOBAL')
        same_side = actor.is_player == target.is_player
        if target_type == 'SELF':
            return actor.pk == target.pk
        if target_type in ('ALLY', 'A_AREA'):
            return same_side
        if target_type in ('ENEMY', 'E_AREA'):
            return not same_side
        if target_type == 'GLOBAL':
            return True
        return False

    @staticmethod
    def _resolve_skill_targets(actor: Combatant, target, target_type: str) -> list[Combatant]:
        """Resolve a skill target declaration into living combatants in field order."""
        combatants = actor.combat_instance.combatants.filter(current_hp__gt=0).order_by('position')

        if target_type == 'SELF':
            if target is not None and target.pk != actor.pk:
                return []
            return [actor]
        if target_type == 'ENEMY':
            if target is None or target.current_hp <= 0 or actor.is_player == target.is_player:
                return []
            return [target]
        if target_type == 'ALLY':
            if target is None or target.current_hp <= 0 or actor.is_player != target.is_player:
                return []
            return [target]
        if target_type == 'E_AREA':
            return list(combatants.filter(is_player=not actor.is_player))
        if target_type == 'A_AREA':
            return list(combatants.filter(is_player=actor.is_player))
        if target_type == 'GLOBAL':
            return list(combatants)
        return []

    @staticmethod
    def _apply_skill_effect(combatant: Combatant, target: Combatant, effect_tmpl) -> str:
        """Apply one effect template to one target and return a log suffix."""
        existing = ActiveEffect.objects.filter(
            combat_instance=combatant.combat_instance,
            target=target,
            effect_template=effect_tmpl,
        ).first()

        if not existing:
            ActiveEffect.objects.create(
                combat_instance=combatant.combat_instance,
                target=target,
                effect_template=effect_tmpl,
                remaining_turns=effect_tmpl.duration_turns,
                remaining_shield_points=effect_tmpl.shields_points,
                caster=combatant,
            )
            return f"Applied {effect_tmpl.name}."

        stacking = effect_tmpl.stacking_rule
        if stacking == 'REFRESH':
            existing.remaining_turns = effect_tmpl.duration_turns
            existing.remaining_shield_points = effect_tmpl.shields_points
            existing.save(update_fields=['remaining_turns', 'remaining_shield_points'])
            return f"Refreshed {effect_tmpl.name}."
        if stacking == 'INDEPENDENT':
            ActiveEffect.objects.create(
                combat_instance=combatant.combat_instance,
                target=target,
                effect_template=effect_tmpl,
                remaining_turns=effect_tmpl.duration_turns,
                remaining_shield_points=effect_tmpl.shields_points,
                caster=combatant,
            )
            return f"Applied additional stack of {effect_tmpl.name}."
        if stacking == 'UPGRADE':
            existing.current_stacks += 1
            existing.remaining_turns = effect_tmpl.duration_turns
            existing.remaining_shield_points = effect_tmpl.shields_points
            existing.save(update_fields=[
                'current_stacks', 'remaining_turns', 'remaining_shield_points',
            ])
            return f"Upgraded {effect_tmpl.name} to {existing.current_stacks} stacks."
        return f"{effect_tmpl.name} is already active."

    @staticmethod
    def _apply_skill_to_target(
        combatant: Combatant,
        target: Combatant,
        template,
        total_damage,
        attacker_mods,
        bonus_final_damage,
        level_damage_multiplier,
    ) -> dict:
        """Apply one cast to one resolved target without charging cast resources."""
        target_name = (
            str(target.entity.name)
            if hasattr(target.entity, 'name')
            else str(target.entity)
        )
        target_result = {
            'target_id': target.id,
            'target_type': 'character' if target.is_player else 'enemy',
            'target': target_name,
            'damage': 0,
            'heal': 0,
            'is_dead': False,
            'effect': None,
            'effect_message': '',
        }
        target_mods = BattleService.get_combat_modifiers(target)

        if template.effect_type == 'DAMAGE':
            buffed_damage = total_damage + attacker_mods['flat_att']
            buffed_damage = int(buffed_damage * (1 + attacker_mods['percent_att']))
            skill_damage = (buffed_damage * template.power_ratio) + template.base_power
            skill_damage *= level_damage_multiplier
            skill_damage *= 1 + bonus_final_damage + attacker_mods['final_damage_modifier']
            skill_damage *= 1 + attacker_mods['damage_dealt_modifier']
            skill_damage *= 1 + target_mods['damage_taken_modifier']
            target_result['damage'] = BattleService.apply_damage_with_shield(
                target, max(0, int(skill_damage))
            )
        elif template.effect_type == 'HEAL':
            heal = (total_damage * template.power_ratio) + template.base_power
            heal *= 1 + attacker_mods['health_dealt_modifier']
            heal *= 1 + target_mods['health_received_modifier']
            hp_before = target.current_hp
            max_hp = getattr(
                target.entity,
                'total_hp',
                getattr(target.entity, 'base_hp', target.current_hp),
            )
            target.current_hp = min(max_hp, target.current_hp + max(0, int(heal)))
            target.save(update_fields=['current_hp'])
            target_result['heal'] = target.current_hp - hp_before

        if template.applies_effect and target.current_hp > 0:
            target_result['effect'] = template.applies_effect.name
            target_result['effect_message'] = BattleService._apply_skill_effect(
                combatant, target, template.applies_effect
            )

        if target.current_hp <= 0:
            target.current_hp = 0
            target.save(update_fields=['current_hp'])
            target_result['is_dead'] = True

        if template.effect_type == 'DAMAGE':
            message = f"dealt {target_result['damage']} damage to {target_name}"
        elif template.effect_type == 'HEAL':
            message = f"healed {target_name} for {target_result['heal']} HP"
        else:
            message = f"affected {target_name}"
        if target_result['effect_message']:
            message += f" ({target_result['effect_message']})"
        if target_result['is_dead']:
            message += f"; {target_name} was defeated"
        target_result['message'] = message
        return target_result

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
        # (C-7 fix) Dynamically calculate start position to avoid collision with party positions
        # Previously hardcoded to 5, which crashes if a party member occupies position 5
        used_positions = list(
            combat_instance.combatants.filter(is_player=True).values_list('position', flat=True)
        )
        enemy_start_position = (max(used_positions) + 1) if used_positions else 1
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
        events = []
        if combat_instance.turn_phase == CombatInstance.TURN_PHASE.PLAYER_PHASE:
            # Find next player
            next_player = combat_instance.combatants.filter(
                is_player=True, 
                position__gt=combat_instance.current_player_position,
                current_hp__gt=0
            ).order_by('position').first()

            if next_player:
                combat_instance.current_player_position = next_player.position
                combat_instance.save()
            else:
                # No more players this round, switch to Monster Phase
                combat_instance.turn_phase = CombatInstance.TURN_PHASE.MONSTER_PHASE
                first_player = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).order_by('position').first()
                if first_player:
                    combat_instance.current_player_position = first_player.position
                
                # (M6 fix) Save before monster phase — monster phase will call end_turn again
                # which handles its own save, avoiding double save
                combat_instance.save()
                
                # Trigger Monster Actions (AI) — this calls end_turn internally
                events.extend(BattleService.process_monster_phase(combat_instance))

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
            
            # (H-1 fix) Process DOT/HOT effects BEFORE picking first_player.
            # If DOT kills the first player, we then correctly skip them below.
            BattleService.process_active_effects(combat_instance)
            
            # (H-1 fix) Re-query alive players AFTER effects have been applied
            first_player = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).order_by('position').first()
            if first_player:
                combat_instance.current_player_position = first_player.position
            
            combat_instance.save()

        return events


    @staticmethod
    def process_monster_phase(combat_instance: CombatInstance):
        """
        AI logic for monsters. Respects skill target_type for smarter behavior.
        """
        import random
        logs = []
        monsters = list(combat_instance.combatants.filter(is_player=False, current_hp__gt=0).order_by('position'))
        players = list(combat_instance.combatants.filter(is_player=True, current_hp__gt=0))

        if not players:
            return logs

        for monster in monsters:
            alive_players = [p for p in players if p.current_hp > 0]
            alive_monsters = [m for m in monsters if m.current_hp > 0]
            
            if not alive_players:
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

            if chosen_skill:
                # Smart target selection based on target_type
                target_type = chosen_skill.target_type
                
                if target_type == 'SELF':
                    target = monster
                elif target_type == 'ALLY':
                    # Ally = other monsters. Pick lowest HP monster for heals/buffs
                    # (C4 fix) Guard against empty alive_monsters list
                    if not alive_monsters:
                        target = monster
                    elif chosen_skill.effect_type == 'HEAL':
                        target = min(alive_monsters, key=lambda m: m.current_hp)
                    else:
                        target = random.choice(alive_monsters)
                elif target_type == 'ENEMY':
                    target = random.choice(alive_players)
                elif target_type in ('E_AREA', 'A_AREA', 'GLOBAL'):
                    # Area scopes are resolved centrally by execute_action.
                    target = None
                else:
                    # Unknown target types fall back to a single opponent.
                    target = random.choice(alive_players)
                
                log = BattleService.execute_action(
                    monster, 'SKILL', target, skill_template_id=chosen_skill.id
                )
                logs.append(log)
                cooldowns[str(chosen_skill.id)] = chosen_skill.cooldown
            else:
                target = random.choice(alive_players)
                log = BattleService.execute_action(monster, 'ATTACK', target)
                logs.append(log)

            monster.skill_cooldowns = cooldowns
            monster.save(update_fields=['skill_cooldowns'])

        # The final monster action may have ended combat. Do not reopen a
        # defeated battle by advancing it back into the player phase.
        combat_instance.refresh_from_db(fields=['status', 'turn_phase'])
        if combat_instance.status == CombatInstance.CombatStatus.IN_PROGRESS:
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
        Process all active effects for the combat instance at the start of a new round.
        Applies per-turn HP/MP changes (DOT/HOT), then decrements duration.
        Returns a list of effect logs.
        """
        effect_logs = []
        effects = list(ActiveEffect.objects.filter(
            combat_instance=combat_instance
        ).select_related('effect_template', 'target'))
        
        # (M4 fix) Batch-resolve entities to avoid N+1 queries
        targets = [e.target for e in effects if e.target]
        _prefetch_entities(targets)
        
        for effect in effects:
            template = effect.effect_template
            target = effect.target
            
            # Skip effects on dead targets
            if target.current_hp <= 0:
                effect.delete()
                continue
            
            log = {
                "effect": template.name,
                "target": str(target.entity.name) if hasattr(target.entity, 'name') else str(target.entity),
                "hp_change": 0,
                "mp_change": 0,
            }
            
            # Apply per-turn HP change (negative = DOT, positive = HOT)
            if template.hp_change_per_turn != 0:
                hp_change = template.hp_change_per_turn
                target.current_hp += hp_change
                
                # Cap HP
                max_hp = getattr(target.entity, 'total_hp', getattr(target.entity, 'base_hp', 9999))
                if target.current_hp > max_hp:
                    target.current_hp = max_hp
                if target.current_hp < 0:
                    target.current_hp = 0
                
                target.save(update_fields=['current_hp'])
                log["hp_change"] = hp_change

            # Percentage DOT scales from the caster's damage and uses the
            # normal shield/damage modifier pipeline.
            if (
                template.damage_power_ratio_per_turn > 0
                and effect.caster
                and target.current_hp > 0
            ):
                caster = effect.caster
                caster_entity = caster.entity
                caster_damage = (
                    caster_entity.total_damage
                    if caster.is_player
                    else getattr(caster_entity, 'base_att', 0)
                )
                caster_mods = BattleService.get_combat_modifiers(caster)
                target_mods = BattleService.get_combat_modifiers(target)
                dot_damage = caster_damage * template.damage_power_ratio_per_turn
                dot_damage *= 1 + caster_mods['final_damage_modifier']
                dot_damage *= 1 + caster_mods['damage_dealt_modifier']
                dot_damage *= 1 + target_mods['damage_taken_modifier']
                actual_damage = BattleService.apply_damage_with_shield(
                    target, max(0, int(dot_damage))
                )
                log["hp_change"] -= actual_damage
                log["damage"] = actual_damage
            
            # Apply per-turn MP change
            if template.mp_change_per_turn != 0:
                mp_change = template.mp_change_per_turn
                target.current_mp += mp_change
                
                max_mp = getattr(target.entity, 'total_mp', getattr(target.entity, 'base_mp', 9999))
                if target.current_mp > max_mp:
                    target.current_mp = max_mp
                if target.current_mp < 0:
                    target.current_mp = 0
                
                target.save(update_fields=['current_mp'])
                log["mp_change"] = mp_change
            
            effect_logs.append(log)
            
            # Decrement remaining turns
            effect.remaining_turns -= 1
            if effect.remaining_turns <= 0:
                effect.delete()
            else:
                effect.save(update_fields=['remaining_turns'])
            
            # Check if target died from DOT
            if target.current_hp <= 0:
                BattleService.check_combat_status(combat_instance)
        
        return effect_logs

    @staticmethod
    def get_combat_modifiers(combatant: Combatant) -> dict:
        """
        (S2 fix) Aggregates all active effect stat modifiers on a combatant.
        Returns a dict of combined modifiers for use in damage/heal calculations.
        """
        mods = {
            'flat_att': 0, 'percent_att': 0.0,
            'flat_str': 0, 'percent_str': 0.0,
            'flat_agi': 0, 'percent_agi': 0.0,
            'flat_int': 0, 'percent_int': 0.0,
            'damage_dealt_modifier': 0.0,
            'damage_taken_modifier': 0.0,
            'final_damage_modifier': 0.0,
            'health_received_modifier': 0.0,
            'health_dealt_modifier': 0.0,
        }
        
        for effect in combatant.active_effects.select_related('effect_template').all():
            t = effect.effect_template
            stacks = effect.current_stacks
            
            mods['flat_att'] += t.flat_att_change * stacks
            mods['percent_att'] += t.percent_att_change * stacks
            mods['flat_str'] += t.flat_str_change * stacks
            mods['percent_str'] += t.percent_str_change * stacks
            mods['flat_agi'] += t.flat_agi_change * stacks
            mods['percent_agi'] += t.percent_agi_change * stacks
            mods['flat_int'] += t.flat_int_change * stacks
            mods['percent_int'] += t.percent_int_change * stacks
            mods['damage_dealt_modifier'] += t.damage_dealt_modifier * stacks
            mods['damage_taken_modifier'] += t.damage_taken_modifier * stacks
            mods['final_damage_modifier'] += t.final_damage_modifier * stacks
            mods['health_received_modifier'] += t.health_received_modifier * stacks
            mods['health_dealt_modifier'] += t.health_dealt_modifier * stacks
        
        return mods

    @staticmethod
    def execute_action(combatant: Combatant, action_type: str, target: Combatant = None, **kwargs):
        """
        Executes an action (Attack, Skill).
        Returns a dict describing the result of the action (combat log).
        Key 'success' is False when the action was blocked (cooldown, MP, dead actor)
        so callers can skip advancing the turn.
        """
        result_log = {
            "actor_id": combatant.id,
            "actor_type": "character" if combatant.is_player else "enemy",
            "actor": str(combatant.entity.name) if hasattr(combatant.entity, 'name') else str(combatant.entity),
            "target_id": target.id if target else None,
            "target_type": ('character' if target.is_player else 'enemy') if target else None,
            "target": (
                str(target.entity.name) if hasattr(target.entity, 'name') else str(target.entity)
            ) if target else None,
            "action": action_type,
            "damage": 0,
            "heal": 0,
            "total_damage": 0,
            "total_heal": 0,
            "targets": [],
            "is_dead": False,
            "message": "",
            "success": True,   # default True; set False when action is blocked
        }

        # (H-2 fix) Dead actor → block action, do NOT consume turn
        if combatant.current_hp <= 0:
            result_log["message"] = f"{result_log['actor']} tried to act but is dead."
            result_log["success"] = False
            return result_log
            
        if action_type == 'ATTACK' and target is None:
            result_log["message"] = "Basic attacks require a target."
            result_log["success"] = False
            return result_log

        # Skill target validation happens after its target scope is known.
        if action_type == 'ATTACK' and target.current_hp <= 0:
            result_log["message"] = f"{result_log['target']} is already dead."
            result_log["success"] = False
            return result_log


        attacker_entity = combatant.entity

        # Reroute Player ATTACK to their Basic Attack SKILL if they have one
        if action_type == 'ATTACK' and combatant.is_player:
            basic_skill = attacker_entity.skills.filter(
                skill_template__is_basic_attack=True,
                skill_template__availability__in=['PLAYER', 'BOTH'],
            ).first()
            if basic_skill:
                action_type = 'SKILL'
                kwargs['character_skill_id'] = basic_skill.id

        # Target modifiers are resolved per target for area skills.
        attacker_mods = BattleService.get_combat_modifiers(combatant)

        if action_type == 'ATTACK':
            if combatant.is_player == target.is_player:
                result_log["message"] = "Basic attacks must target an opponent."
                result_log["success"] = False
                return result_log
            if combatant.is_player:
                damage = int(attacker_entity.total_damage)
                skill_name = "Đánh thường"
            else:
                damage = int(getattr(attacker_entity, 'base_att', 10))
                skill_name = "Đánh thường"
            
            # Apply active effect modifiers to basic attack
            target_mods = BattleService.get_combat_modifiers(target)
            damage = int(damage * (1 + attacker_mods['damage_dealt_modifier'])
                               * (1 + target_mods['damage_taken_modifier']))
            if damage < 0:
                damage = 0
            
            actual_damage = BattleService.apply_damage_with_shield(target, damage)
            
            result_log["damage"] = actual_damage
            result_log["total_damage"] = actual_damage
            result_log["targets"] = [{
                'target_id': target.id,
                'target_type': 'character' if target.is_player else 'enemy',
                'target': result_log['target'],
                'damage': actual_damage,
                'heal': 0,
                'is_dead': target.current_hp <= 0,
                'effect': None,
                'effect_message': '',
                'message': f"dealt {actual_damage} damage to {result_log['target']}",
            }]
            result_log["message"] = f"{result_log['actor']} used {skill_name} and dealt {actual_damage} damage to {result_log['target']}."

        elif action_type == 'SKILL':
            if combatant.is_player:
                character_skill_id = kwargs.get('character_skill_id') or kwargs.get('skill_id')
                if not character_skill_id:
                    result_log["message"] = "No character skill provided."
                    result_log["success"] = False
                    return result_log
                from apps.characters.models import CharacterSkill
                try:
                    char_skill = CharacterSkill.objects.select_related('skill_template').get(
                        id=character_skill_id,
                        character=attacker_entity,
                    )
                except CharacterSkill.DoesNotExist:
                    result_log["message"] = "Skill not found for this character."
                    result_log["success"] = False
                    return result_log
                template = char_skill.skill_template
                if template.availability not in ('PLAYER', 'BOTH'):
                    result_log["message"] = "This skill cannot be used by players."
                    result_log["success"] = False
                    return result_log
                bonus_final_damage = char_skill.bonus_final_damage
                total_damage = attacker_entity.total_damage
                
                # Check player cooldown
                current_cd = combatant.skill_cooldowns.get(str(template.id), 0)
                if current_cd > 0:
                    result_log["message"] = f"{template.name} is on cooldown for {current_cd} more turns."
                    result_log["success"] = False
                    return result_log
            else:
                skill_template_id = kwargs.get('skill_template_id') or kwargs.get('skill_id')
                if not skill_template_id:
                    result_log["message"] = "No enemy skill provided."
                    result_log["success"] = False
                    return result_log
                from apps.skilles.models import SkillTemplate
                try:
                    template = SkillTemplate.objects.get(id=skill_template_id)
                except SkillTemplate.DoesNotExist:
                    result_log["message"] = "Skill not found."
                    result_log["success"] = False
                    return result_log
                if template.availability not in ('ENEMY', 'BOTH'):
                    result_log["message"] = "This skill cannot be used by enemies."
                    result_log["success"] = False
                    return result_log
                bonus_final_damage = 0.0
                total_damage = getattr(attacker_entity, 'base_att', 10)

            if not BattleService._is_valid_skill_target(combatant, target, template.target_type):
                result_log["message"] = f"{template.name} cannot target {result_log['target']}."
                result_log["success"] = False
                return result_log

            resolved_targets = BattleService._resolve_skill_targets(
                combatant, target, template.target_type
            )
            if not resolved_targets:
                result_log["message"] = f"{template.name} has no valid living targets."
                result_log["success"] = False
                return result_log
            _prefetch_entities(resolved_targets)

            # Area skills may omit a primary target. Keep the legacy top-level
            # target fields populated with the first resolved target.
            primary_target = target if target in resolved_targets else resolved_targets[0]
            result_log["target_id"] = primary_target.id
            result_log["target_type"] = 'character' if primary_target.is_player else 'enemy'
            result_log["target"] = (
                str(primary_target.entity.name)
                if hasattr(primary_target.entity, 'name')
                else str(primary_target.entity)
            )

            # Check MP
            if combatant.current_mp < template.mp_cost:
                result_log["message"] = f"Not enough MP to use {template.name}."
                result_log["success"] = False
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
            result_log["character_skill_id"] = char_skill.id if combatant.is_player else None
            result_log["skill_template_id"] = template.id
            result_log["skill_visual_key"] = template.visual_key
            result_log["skill_target_type"] = template.target_type

            level_damage_multiplier = 1.0
            if combatant.is_player:
                from apps.skilles.models import SkillLevelConfig
                level_config = SkillLevelConfig.objects.filter(
                    skill=template, skill_level=char_skill.level
                ).first()
                if level_config:
                    level_damage_multiplier = level_config.damage_multiplier

            target_results = [
                BattleService._apply_skill_to_target(
                    combatant=combatant,
                    target=resolved_target,
                    template=template,
                    total_damage=total_damage,
                    attacker_mods=attacker_mods,
                    bonus_final_damage=bonus_final_damage,
                    level_damage_multiplier=level_damage_multiplier,
                )
                for resolved_target in resolved_targets
            ]
            result_log["targets"] = target_results
            result_log["damage"] = sum(item['damage'] for item in target_results)
            result_log["heal"] = sum(item['heal'] for item in target_results)
            result_log["total_damage"] = result_log["damage"]
            result_log["total_heal"] = result_log["heal"]
            result_log["is_dead"] = any(item['is_dead'] for item in target_results)
            result_log["message"] = (
                f"{result_log['actor']} used {template.name}: "
                + '; '.join(item['message'] for item in target_results)
                + '.'
            )

        # Single basic attacks are handled outside the skill target loop.
        if action_type == 'ATTACK' and target.current_hp <= 0:
            target.current_hp = 0
            # (H-3 fix) Use update_fields to avoid overwriting concurrent state changes
            # (e.g. skill cooldowns updated in the same round) with stale in-memory values.
            # apply_damage_with_shield already saved current_hp=0; this ensures it stays 0.
            target.save(update_fields=['current_hp'])
            result_log["is_dead"] = True
            result_log["targets"][0]["is_dead"] = True
            result_log["message"] += f" {result_log['target']} has been defeated!"

            
        # Check combat status after action
        battle_result = BattleService.check_combat_status(combatant.combat_instance)
        if battle_result["status"] != CombatInstance.CombatStatus.IN_PROGRESS:
            result_log["battle_result"] = {
                "status": battle_result["status"],
                "rewards": battle_result["logs"],
            }
        
        return result_log

    @staticmethod
    def check_combat_status(combat_instance) -> dict:
        """
        Check if the combat has ended (all players dead or all enemies dead).
        Returns a dict with 'status' (ONGOING, VICTORY, DEFEAT) and 'logs' (if any rewards distributed).
        """
        # (C2 fix) Guard: skip if combat already ended to prevent duplicate rewards
        if combat_instance.status != 'in_progress':
            return {"status": combat_instance.status, "logs": None}
        
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
