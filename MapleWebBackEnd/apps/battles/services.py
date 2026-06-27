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
        for index, enemy_template in enumerate(enemies):
            Combatant.objects.create(
                combat_instance=combat_instance,
                content_type=ContentType.objects.get_for_model(enemy_template),
                objects_id=enemy_template.id,
                entity=enemy_template,
                is_player=False,
                current_hp=enemy_template.base_hp,
                current_mp=enemy_template.base_mp,
                position=enemy_start_position + index
            )
        
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
                
                # Trigger Monster Actions (Placeholder for AI)
                # For now, we just switch back to player phase immediately or handle it elsewhere
                # But let's assume we want to process monster turns here or let a separate call handle it.
                # To keep it simple, we'll just switch back to Player Phase for now, 
                # effectively simulating a "Monsters did nothing" or "Monsters act instantly"
                
                # Realistically, we might want to return here and let the controller call 'process_monster_turn'
                pass

        elif combat_instance.turn_phase == CombatInstance.TURN_PHASE.MONSTER_PHASE:
            # Switch back to Player Phase
            combat_instance.turn_phase = CombatInstance.TURN_PHASE.PLAYER_PHASE
            combat_instance.turn_count += 1
            
            # Reset to first player
            first_player = combat_instance.combatants.filter(is_player=True, current_hp__gt=0).order_by('position').first()
            if first_player:
                combat_instance.current_player_position = first_player.position
            
            # Process effects at start of round
            BattleService.process_active_effects(combat_instance)
        
        combat_instance.save()

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
        Executes an action (Attack, Skill, Item).
        """
        if action_type == 'ATTACK':
            # Basic attack logic
            # Calculate damage based on combatant stats
            # Since combatant.entity can be Character or EnemyTemplate, we need to handle both
            
            attacker_entity = combatant.entity
            target_entity = target.entity
            
            # Simple damage formula placeholder
            # If entity has 'total_att' (Character) or 'base_att' (Enemy)
            att = getattr(attacker_entity, 'total_att', getattr(attacker_entity, 'base_att', 10))
            
            damage = att # Very basic 1:1 damage
            
            target.current_hp -= damage
            target.save()
            
        elif action_type == 'SKILL':
            # Skill logic
            pass
            
        # Check for death
        if target.current_hp <= 0:
            target.current_hp = 0
            target.save()
            # Handle death (remove from combat or mark dead)
            
        # Check combat status after action
        BattleService.check_combat_status(combatant.combat_instance)

    @staticmethod
    def check_combat_status(combat_instance: CombatInstance) -> str:
        """
        Checks if the combat has ended.
        """
        players = Combatant.objects.filter(combat_instance=combat_instance, is_player=True, current_hp__gt=0)
        enemies = Combatant.objects.filter(combat_instance=combat_instance, is_player=False, current_hp__gt=0)

        if not players.exists():
            combat_instance.status = CombatInstance.CombatStatus.DEFEAT
            combat_instance.save()
            return 'DEFEAT'
        
        if not enemies.exists():
            combat_instance.status = CombatInstance.CombatStatus.VICTORY
            combat_instance.save()
            return 'VICTORY'
            
        return 'IN_PROGRESS'
