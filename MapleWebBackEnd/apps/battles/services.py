from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
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
            combatants__has_left=False,
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
    def _dispel(caster: Combatant, target: Combatant, count: int) -> list[str]:
        """
        Remove up to `count` dispellable effects, newest first: debuffs from
        the caster's own side, buffs from the other side. Returns their names.
        """
        from apps.skilles.models import EffectTemplate

        kind = (
            EffectTemplate.Kind.DEBUFF if caster.is_player == target.is_player
            else EffectTemplate.Kind.BUFF
        )
        removed = list(
            target.active_effects.filter(
                effect_template__dispellable=True, effect_template__effect_kind=kind,
            ).select_related('effect_template').order_by('-created_at', '-id')[:count]
        )
        for effect in removed:
            effect.delete()
        if removed:
            BattleService.clamp_to_max(target)
        return [effect.effect_template.name for effect in removed]

    @staticmethod
    def _apply_skill_effect(combatant: Combatant, target: Combatant, effect_tmpl) -> str:
        """Apply one effect template to one target and return a log suffix."""
        messages = []
        if effect_tmpl.dispel_count:
            removed = BattleService._dispel(combatant, target, effect_tmpl.dispel_count)
            messages.append(f"Dispelled {', '.join(removed)}." if removed else "Nothing to dispel.")
        if effect_tmpl.duration_turns <= 0:
            # Instant effect (e.g. a pure dispel): nothing stays on the target.
            return ' '.join(messages) or f"Applied {effect_tmpl.name}."

        combat = combatant.combat_instance
        # Applied during the target side's own phase: that phase is not one of its turns.
        skip_next_tick = target.is_player == (
            combat.turn_phase == CombatInstance.TURN_PHASE.PLAYER_PHASE
        )
        existing = ActiveEffect.objects.filter(
            combat_instance=combat,
            target=target,
            effect_template=effect_tmpl,
        ).first()
        stacking = effect_tmpl.stacking_rule

        if not existing or stacking == 'INDEPENDENT':
            ActiveEffect.objects.create(
                combat_instance=combat,
                target=target,
                effect_template=effect_tmpl,
                remaining_turns=effect_tmpl.duration_turns,
                remaining_shield_points=effect_tmpl.shields_points,
                caster=combatant,
                skip_next_tick=skip_next_tick,
            )
            messages.append(
                f"Applied additional stack of {effect_tmpl.name}." if existing
                else f"Applied {effect_tmpl.name}."
            )
        elif stacking in ('REFRESH', 'UPGRADE'):
            existing.remaining_turns = effect_tmpl.duration_turns
            existing.remaining_shield_points = effect_tmpl.shields_points
            existing.skip_next_tick = skip_next_tick
            if stacking == 'UPGRADE':
                existing.current_stacks += 1
            existing.save(update_fields=[
                'current_stacks', 'remaining_turns', 'remaining_shield_points', 'skip_next_tick',
            ])
            messages.append(
                f"Upgraded {effect_tmpl.name} to {existing.current_stacks} stacks." if stacking == 'UPGRADE'
                else f"Refreshed {effect_tmpl.name}."
            )
        else:
            messages.append(f"{effect_tmpl.name} is already active.")

        # A max HP/MP debuff can leave the target above its new maximum.
        BattleService.clamp_to_max(target)
        return ' '.join(messages)

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
            'shield_absorbed': 0,
            'heal': 0,
            'is_dead': False,
            'effect': None,
            'effect_message': '',
        }
        target_mods = BattleService.get_combat_modifiers(target)

        if template.effect_type == 'DAMAGE':
            # total_damage already includes the attacker's stat/ATT effects.
            skill_damage = (total_damage * template.power_ratio) + template.base_power
            skill_damage *= level_damage_multiplier
            skill_damage *= 1 + bonus_final_damage + attacker_mods['final_damage_modifier']
            skill_damage *= 1 + attacker_mods['damage_dealt_modifier']
            skill_damage *= 1 + target_mods['damage_taken_modifier']
            raw_damage = max(0, int(skill_damage))
            target_result['damage'] = BattleService.apply_damage_with_shield(target, raw_damage)
            target_result['shield_absorbed'] = raw_damage - target_result['damage']
        elif template.effect_type == 'HEAL':
            heal = (total_damage * template.power_ratio) + template.base_power
            heal *= 1 + attacker_mods['health_dealt_modifier']
            heal *= 1 + target_mods['health_received_modifier']
            hp_before = target.current_hp
            max_hp = BattleService.get_max_hp(target, target_mods)
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
        combat_instance.turn_started_at = timezone.now()

        combat_instance.save()

    # A stun lock could otherwise chain rounds forever inside one request.
    MAX_STUN_SKIPS_PER_REQUEST = 30

    @staticmethod
    def end_turn(combat_instance: CombatInstance):
        """
        Ends the current turn.
        If Player Phase: moves to the next player, or ends the phase and runs the Monster Phase.
        If Monster Phase: ends it and starts the next round's Player Phase.
        Effects tick at the end of their target side's phase.
        """
        events = []
        if combat_instance.turn_phase == CombatInstance.TURN_PHASE.PLAYER_PHASE:
            events.extend(BattleService._advance_player_turn(
                combat_instance, after_position=combat_instance.current_player_position,
            ))

        elif combat_instance.turn_phase == CombatInstance.TURN_PHASE.MONSTER_PHASE:
            # End of the monster phase: effects on monsters tick; a tick can end the battle.
            events.extend(BattleService.process_active_effects(combat_instance, players=False))
            if combat_instance.status != CombatInstance.CombatStatus.IN_PROGRESS:
                return events

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

            events.extend(BattleService._advance_player_turn(combat_instance))

        return events

    @staticmethod
    def _advance_player_turn(combat_instance: CombatInstance, after_position=None):
        """
        Give the turn to the next living, non-stunned player after `after_position`
        (from the first one when None). Stunned players lose their turn. With
        nobody left, the player phase ends: effects on players tick, then the
        monster phase runs.
        """
        events = []
        players = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).order_by('position')
        if after_position is not None:
            players = players.filter(position__gt=after_position)

        for player in players:
            skips = getattr(combat_instance, '_stun_skips', 0)
            if skips < BattleService.MAX_STUN_SKIPS_PER_REQUEST and BattleService.is_stunned(player):
                combat_instance._stun_skips = skips + 1
                events.append(BattleService.stunned_turn_event(player))
                continue
            combat_instance.current_player_position = player.position
            combat_instance.turn_started_at = timezone.now()
            combat_instance.save()
            return events

        # End of the player phase: effects on players tick; a tick can end the battle.
        events.extend(BattleService.process_active_effects(combat_instance, players=True))
        if combat_instance.status != CombatInstance.CombatStatus.IN_PROGRESS:
            return events

        combat_instance.turn_phase = CombatInstance.TURN_PHASE.MONSTER_PHASE
        first_player = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).order_by('position').first()
        if first_player:
            combat_instance.current_player_position = first_player.position
        # (M6 fix) Save before monster phase — monster phase will call end_turn again
        combat_instance.save()

        # Trigger Monster Actions (AI) — this calls end_turn internally
        events.extend(BattleService.process_monster_phase(combat_instance))
        return events


    @staticmethod
    def process_monster_phase(combat_instance: CombatInstance):
        """
        AI logic for monsters. Respects skill target_type for smarter behavior.
        """
        import random
        logs = []
        if not combat_instance.combatants.filter(is_player=True, current_hp__gt=0).exists():
            return logs

        monster_ids = list(
            combat_instance.combatants.filter(is_player=False, current_hp__gt=0)
            .order_by('position').values_list('id', flat=True)
        )
        for monster_id in monster_ids:
            # Earlier actions this phase (area skills, heals, kills) were saved
            # through other Combatant instances. Reload so this monster neither
            # acts after dying nor overwrites HP changes with stale values.
            living = list(combat_instance.combatants.filter(current_hp__gt=0))
            _prefetch_entities(living)
            monster = next((c for c in living if c.pk == monster_id), None)
            if monster is None:
                continue
            alive_players = [c for c in living if c.is_player]
            alive_monsters = [c for c in living if not c.is_player]

            if not alive_players:
                break

            cooldowns = monster.skill_cooldowns
            for skill_id in list(cooldowns.keys()):
                if cooldowns[skill_id] > 0:
                    cooldowns[skill_id] -= 1

            if BattleService.is_stunned(monster):
                logs.append(BattleService.stunned_turn_event(monster))
                monster.skill_cooldowns = cooldowns
                monster.save(update_fields=['skill_cooldowns'])
                continue

            enemy_template = monster.entity
            monster_mods = BattleService.get_combat_modifiers(monster)
            # Silenced monsters fall back to a basic attack.
            enemy_skills = [] if BattleService.is_silenced(monster) else enemy_template.enemy_skills.all()
            available_skills = []
            for es in enemy_skills:
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
                cooldowns[str(chosen_skill.id)] = BattleService.skill_cooldown_after_use(
                    chosen_skill, monster_mods
                )
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
            logs.extend(BattleService.end_turn(combat_instance))
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
    def process_active_effects(combat_instance: CombatInstance, players=None):
        """
        Tick active effects at the end of a side's phase: effects on players
        (players=True) or on monsters (players=False); None ticks both.
        Applies per-turn HP/MP changes (DOT/HOT), then decrements duration.
        An effect applied during this same phase skips this one tick.
        Returns a list of effect logs.
        """
        effect_logs = []
        effects = ActiveEffect.objects.filter(
            combat_instance=combat_instance
        ).select_related('effect_template')
        if players is not None:
            effects = effects.filter(target__is_player=players)
        effects = list(effects)

        # One shared instance per combatant: effects stacked on the same target
        # must build on each other's HP/MP changes instead of each saving a
        # separately loaded copy.
        targets_by_id = {
            combatant.pk: combatant
            for combatant in combat_instance.combatants.filter(
                pk__in={effect.target_id for effect in effects}
            )
        }
        # (M4 fix) Batch-resolve entities to avoid N+1 queries
        _prefetch_entities(list(targets_by_id.values()))

        for effect in effects:
            template = effect.effect_template
            target = targets_by_id[effect.target_id]
            
            # Skip effects on dead targets
            if target.current_hp <= 0:
                effect.delete()
                continue

            if effect.skip_next_tick:
                effect.skip_next_tick = False
                effect.save(update_fields=['skip_next_tick'])
                continue

            log = {
                "event_type": "effect_tick",
                "effect_id": effect.id,
                "effect": template.name,
                "target_id": target.id,
                "target_type": 'character' if target.is_player else 'enemy',
                "target": str(target.entity.name) if hasattr(target.entity, 'name') else str(target.entity),
                "hp_change": 0,
                "mp_change": 0,
                "shield_absorbed": 0,
                "is_dead": False,
                "expired": False,
            }
            
            target_mods = BattleService.get_combat_modifiers(target)
            caster_mods = (
                BattleService.get_combat_modifiers(effect.caster) if effect.caster else None
            )

            def restored(amount, kind):
                # Healing/mana over time follows the same modifiers as direct restores.
                if amount <= 0:
                    return amount
                amount *= 1 + target_mods[f'{kind}_received_modifier']
                if caster_mods:
                    amount *= 1 + caster_mods[f'{kind}_dealt_modifier']
                return max(0, int(amount))

            # Apply per-turn HP change (negative = DOT, positive = HOT)
            if template.hp_change_per_turn != 0:
                hp_before = target.current_hp
                target.current_hp += restored(template.hp_change_per_turn, 'health')
                target.current_hp = max(0, min(target.current_hp, BattleService.get_max_hp(target, target_mods)))
                target.save(update_fields=['current_hp'])
                log["hp_change"] = target.current_hp - hp_before

            # Percentage DOT scales from the caster's damage and uses the
            # normal shield/damage modifier pipeline.
            if (
                template.damage_power_ratio_per_turn > 0
                and effect.caster
                and target.current_hp > 0
            ):
                caster_damage = BattleService.get_attack_power(effect.caster, caster_mods)
                dot_damage = caster_damage * template.damage_power_ratio_per_turn
                dot_damage *= 1 + caster_mods['final_damage_modifier']
                dot_damage *= 1 + caster_mods['damage_dealt_modifier']
                dot_damage *= 1 + target_mods['damage_taken_modifier']
                raw_damage = max(0, int(dot_damage))
                actual_damage = BattleService.apply_damage_with_shield(target, raw_damage)
                log["hp_change"] -= actual_damage
                log["damage"] = actual_damage
                log["shield_absorbed"] = raw_damage - actual_damage
            
            # Apply per-turn MP change
            if template.mp_change_per_turn != 0:
                mp_before = target.current_mp
                target.current_mp += restored(template.mp_change_per_turn, 'mana')
                target.current_mp = max(0, min(target.current_mp, BattleService.get_max_mp(target, target_mods)))
                target.save(update_fields=['current_mp'])
                log["mp_change"] = target.current_mp - mp_before

            effect_logs.append(log)

            # Decrement remaining turns
            effect.remaining_turns -= 1
            if effect.remaining_turns <= 0:
                effect.delete()
                log["expired"] = True
                # Losing a max HP/MP buff pulls current HP/MP back under the max.
                BattleService.clamp_to_max(target)
            else:
                effect.save(update_fields=['remaining_turns'])

            # Check if target died from DOT; a tick can end the battle.
            if target.current_hp <= 0:
                log["is_dead"] = True
                battle_result = BattleService.check_combat_status(combat_instance)
                if battle_result["status"] != CombatInstance.CombatStatus.IN_PROGRESS:
                    log["battle_result"] = {
                        "status": battle_result["status"],
                        "rewards": battle_result["logs"],
                    }
                    break

        return effect_logs

    @staticmethod
    def get_combat_modifiers(combatant: Combatant) -> dict:
        """
        (S2 fix) Aggregates all active effect stat modifiers on a combatant.
        Returns a dict of combined modifiers for use in damage/heal calculations.
        """
        mods = {
            'flat_hp': 0, 'percent_hp': 0.0,
            'flat_mp': 0, 'percent_mp': 0.0,
            'flat_att': 0, 'percent_att': 0.0,
            'flat_str': 0, 'percent_str': 0.0,
            'flat_agi': 0, 'percent_agi': 0.0,
            'flat_int': 0, 'percent_int': 0.0,
            'damage_dealt_modifier': 0.0,
            'damage_taken_modifier': 0.0,
            'final_damage_modifier': 0.0,
            'health_received_modifier': 0.0,
            'health_dealt_modifier': 0.0,
            'mana_received_modifier': 0.0,
            'mana_dealt_modifier': 0.0,
            'cooldown_reduction': 0,
        }

        for effect in combatant.active_effects.select_related('effect_template').all():
            t = effect.effect_template
            stacks = effect.current_stacks

            mods['flat_hp'] += t.flat_hp_change * stacks
            mods['percent_hp'] += t.percent_hp_change * stacks
            mods['flat_mp'] += t.flat_mp_change * stacks
            mods['percent_mp'] += t.percent_mp_change * stacks
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
            mods['mana_received_modifier'] += t.mana_received_modifier * stacks
            mods['mana_dealt_modifier'] += t.mana_dealt_modifier * stacks
            mods['cooldown_reduction'] += t.cooldown_reduction * stacks

        return mods

    @staticmethod
    def _max_resource(combatant, resource, mods=None) -> int:
        if mods is None:
            mods = BattleService.get_combat_modifiers(combatant)
        entity = combatant.entity
        base = getattr(entity, f'total_{resource}', None) if combatant.is_player else None
        if base is None:
            base = getattr(entity, f'base_{resource}', 0)
        return max(0, int((base + mods[f'flat_{resource}']) * (1 + mods[f'percent_{resource}'])))

    @staticmethod
    def get_max_hp(combatant, mods=None) -> int:
        """Max HP with active max-HP effects applied (never below 1)."""
        return max(1, BattleService._max_resource(combatant, 'hp', mods))

    @staticmethod
    def get_max_mp(combatant, mods=None) -> int:
        """Max MP with active max-MP effects applied."""
        return BattleService._max_resource(combatant, 'mp', mods)

    @staticmethod
    def clamp_to_max(combatant) -> None:
        """Pull HP/MP back under the max after a max-raising effect ends or a lowering one lands."""
        mods = BattleService.get_combat_modifiers(combatant)
        max_hp = BattleService.get_max_hp(combatant, mods)
        max_mp = BattleService.get_max_mp(combatant, mods)
        if combatant.current_hp > max_hp or combatant.current_mp > max_mp:
            combatant.current_hp = min(combatant.current_hp, max_hp)
            combatant.current_mp = min(combatant.current_mp, max_mp)
            combatant.save(update_fields=['current_hp', 'current_mp'])

    @staticmethod
    def has_special_effect(combatant, tag_id) -> bool:
        return combatant.active_effects.filter(effect_template__special_effects__id=tag_id).exists()

    @staticmethod
    def is_stunned(combatant) -> bool:
        from apps.skilles.models import SpecialEffectTag
        return BattleService.has_special_effect(combatant, SpecialEffectTag.STUN)

    @staticmethod
    def is_silenced(combatant) -> bool:
        from apps.skilles.models import SpecialEffectTag
        return BattleService.has_special_effect(combatant, SpecialEffectTag.SILENCE)

    @staticmethod
    def skill_cooldown_after_use(template, mods) -> int:
        return max(0, template.cooldown - mods['cooldown_reduction'])

    @staticmethod
    def stunned_turn_event(combatant) -> dict:
        name = getattr(combatant.entity, 'name', str(combatant.entity))
        return {
            "event_type": "turn_skipped",
            "actor_id": combatant.id,
            "actor_type": "character" if combatant.is_player else "enemy",
            "actor": name,
            "reason": "stunned",
            "message": f"{name} is stunned and loses the turn.",
        }

    @staticmethod
    def item_cooldown_key(item_template_id) -> str:
        """Key of an item's cooldown in Combatant.skill_cooldowns (next to skill IDs)."""
        return f"item:{item_template_id}"

    @staticmethod
    def _use_item(combatant: Combatant, target, result_log: dict, inventory_item_id) -> None:
        """
        Use one battle consumable from the player's inventory, filling in
        `result_log`. Sets success=False, without consuming anything, when the
        item or target is not valid.
        """
        from apps.inventory.models import InventoryItem
        from apps.inventory.reservations import exclude_reserved
        from apps.items.models import BattleConsumableRule

        def blocked(message):
            result_log["message"] = message
            result_log["success"] = False

        if not combatant.is_player:
            return blocked("Only players can use items.")
        item = exclude_reserved(
            InventoryItem.objects.select_for_update().select_related('template').filter(
                pk=inventory_item_id, owner_id=combatant.objects_id, is_destroyed=False,
            )
        ).first()
        if item is None or item.quantity <= 0:
            return blocked("Item not found or not available.")
        if item.expired_at and item.expired_at <= timezone.now():
            return blocked("Item is expired.")
        try:
            rule = item.template.battle_consumable_rule
        except BattleConsumableRule.DoesNotExist:
            return blocked(f"{item.template.name} cannot be used in battle.")

        cooldown_key = BattleService.item_cooldown_key(item.template_id)
        cooldown_left = combatant.skill_cooldowns.get(cooldown_key, 0)
        if cooldown_left > 0:
            return blocked(f"{item.template.name} is on cooldown for {cooldown_left} more turns.")

        if target is None:
            target = combatant
        if rule.target_type == BattleConsumableRule.TargetType.SELF:
            if target.pk != combatant.pk:
                return blocked(f"{item.template.name} can only be used on yourself.")
        elif not target.is_player or target.current_hp <= 0:
            return blocked(f"{item.template.name} must target yourself or a living ally.")

        entity = target.entity
        target_name = getattr(entity, 'name', str(entity))
        target_mods = BattleService.get_combat_modifiers(target)
        max_hp = BattleService.get_max_hp(target, target_mods)
        max_mp = BattleService.get_max_mp(target, target_mods)
        heal = rule.hp_restore + int(rule.hp_restore_percent * max_hp)
        heal = max(0, int(heal * (1 + target_mods['health_received_modifier'])))
        mana = rule.mp_restore + int(rule.mp_restore_percent * max_mp)
        mana = max(0, int(mana * (1 + target_mods['mana_received_modifier'])))
        hp_before, mp_before = target.current_hp, target.current_mp
        target.current_hp = min(max_hp, target.current_hp + heal)
        target.current_mp = min(max_mp, target.current_mp + mana)
        target.save(update_fields=['current_hp', 'current_mp'])

        effect_message = ''
        if rule.applies_effect:
            effect_message = BattleService._apply_skill_effect(combatant, target, rule.applies_effect)

        item_name = item.template.name
        item.quantity -= 1
        if item.quantity <= 0:
            item.delete()
        else:
            item.save(update_fields=['quantity'])
        if rule.cooldown_turns > 0:
            combatant.skill_cooldowns = {**combatant.skill_cooldowns, cooldown_key: rule.cooldown_turns}
            combatant.save(update_fields=['skill_cooldowns'])

        healed = target.current_hp - hp_before
        restored_mp = target.current_mp - mp_before
        message = f"restored {healed} HP"
        if restored_mp:
            message += f" and {restored_mp} MP"
        message += f" to {target_name}"
        if effect_message:
            message += f" ({effect_message})"
        result_log.update({
            "item_name": item_name,
            "inventory_item_id": inventory_item_id,
            "item_template_id": rule.item_template_id,
            "target_id": target.id,
            "target_type": 'character',
            "target": target_name,
            "heal": healed,
            "total_heal": healed,
            "mp_restored": restored_mp,
            "targets": [{
                'target_id': target.id,
                'target_type': 'character',
                'target': target_name,
                'damage': 0,
                'shield_absorbed': 0,
                'heal': healed,
                'mp_restored': restored_mp,
                'is_dead': False,
                'effect': rule.applies_effect.name if rule.applies_effect else None,
                'effect_message': effect_message,
                'message': message,
            }],
            "message": f"{result_log['actor']} used {item_name}: {message}.",
        })

    @staticmethod
    def get_attack_power(combatant: Combatant, mods: dict = None) -> int:
        """
        Damage basis of a combatant with its active stat effects applied.
        Flat changes add to the stat, then percent changes scale it; players
        then go through the normal damage formula with those stats.
        """
        if mods is None:
            mods = BattleService.get_combat_modifiers(combatant)
        entity = combatant.entity

        def buffed(value, stat):
            return (value + mods[f'flat_{stat}']) * (1 + mods[f'percent_{stat}'])

        if not combatant.is_player:
            return max(0, int(buffed(getattr(entity, 'base_att', 10), 'att')))
        return max(0, int(entity.damage_from(
            str_value=buffed(entity.total_str, 'str'),
            agi_value=buffed(entity.total_agi, 'agi'),
            int_value=buffed(entity.total_int, 'int'),
            att_value=buffed(entity.total_att, 'att'),
        )))

    @staticmethod
    def execute_action(combatant: Combatant, action_type: str, target: Combatant = None, **kwargs):
        """
        Executes an action (Attack, Skill).
        Returns a dict describing the result of the action (combat log).
        Key 'success' is False when the action was blocked (cooldown, MP, dead actor)
        so callers can skip advancing the turn.
        """
        result_log = {
            "event_type": "action",
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

        if action_type == 'ITEM':
            # Restoring HP/MP or buffing cannot end the battle.
            BattleService._use_item(combatant, target, result_log, kwargs.get('inventory_item_id'))
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
            damage = BattleService.get_attack_power(combatant, attacker_mods)
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
                'shield_absorbed': damage - actual_damage,
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
                total_damage = BattleService.get_attack_power(combatant, attacker_mods)
                
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
                total_damage = BattleService.get_attack_power(combatant, attacker_mods)

            # Silence blocks skills; basic attacks (also when routed through a skill) still work.
            if not template.is_basic_attack and BattleService.is_silenced(combatant):
                result_log["message"] = f"{result_log['actor']} is silenced and cannot use {template.name}."
                result_log["success"] = False
                return result_log

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
            
            cooldown = BattleService.skill_cooldown_after_use(template, attacker_mods)
            if combatant.is_player and cooldown > 0:
                cooldowns = combatant.skill_cooldowns
                cooldowns[str(template.id)] = cooldown
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
    def _is_current_actor(combat_instance, combatant) -> bool:
        return (
            combat_instance.turn_phase == CombatInstance.TURN_PHASE.PLAYER_PHASE
            and combatant.position == combat_instance.current_player_position
        )

    @staticmethod
    def forfeit(combat_instance: CombatInstance, combatant: Combatant) -> list:
        """
        Take a player out of the battle. The battle is lost once no player is
        left; otherwise a forfeiting current actor passes the turn on.
        """
        was_current_actor = (
            combatant.current_hp > 0 and BattleService._is_current_actor(combat_instance, combatant)
        )
        combatant.current_hp = 0
        combatant.has_left = True
        combatant.save(update_fields=['current_hp', 'has_left'])
        name = getattr(combatant.entity, 'name', str(combatant.entity))
        event = {
            "event_type": "forfeit",
            "actor_id": combatant.id,
            "actor_type": "character",
            "actor": name,
            "message": f"{name} left the battle.",
        }
        events = [event]

        battle_result = BattleService.check_combat_status(combat_instance)
        if battle_result["status"] != CombatInstance.CombatStatus.IN_PROGRESS:
            event["battle_result"] = {
                "status": battle_result["status"],
                "rewards": battle_result["logs"],
            }
        elif was_current_actor:
            events.extend(BattleService.end_turn(combat_instance))
        return events

    @staticmethod
    def skip_turn(combat_instance: CombatInstance, combatant: Combatant) -> list:
        """Pass an idle current actor's turn without an action."""
        name = getattr(combatant.entity, 'name', str(combatant.entity))
        events = [{
            "event_type": "turn_skipped",
            "actor_id": combatant.id,
            "actor_type": "character",
            "actor": name,
            "reason": "idle",
            "message": f"{name}'s turn was skipped for inactivity.",
        }]
        events.extend(BattleService.end_turn(combat_instance))
        return events

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
