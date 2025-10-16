from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

#Create UUID
import uuid

def generate_hex_id():
    return uuid.uuid4().hex[:8] #Generate a 8-character hex id

class CombatInstance(models.Model):
    id = models.CharField(primary_key=True, max_length=8, default=generate_hex_id, editable=False)

    class CombatStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        VICTORY = 'victory', 'Victory'
        DEFEAT = 'defeat', 'Defeat'

    class TURN_PHASE(models.TextChoices):
        PLAYER_PHASE = 'player_phase', 'Player Phase'
        MONSTER_PHASE = 'monster_phase', 'Monster Phase'

    #Link to party 
    party = models.ForeignKey('party.Party', on_delete=models.CASCADE, related_name='combat_instances')
    current_player_position = models.PositiveIntegerField(default=1) #Track current player position in party for turn order
    #Link to enemy group

    #Status
    status = models.CharField(max_length=20, choices=CombatStatus.choices, default=CombatStatus.IN_PROGRESS)
    turn_phase = models.CharField(max_length=20, choices=TURN_PHASE.choices, default=TURN_PHASE.PLAYER_PHASE, help_text="Current phase of the turn")
    turn_count = models.IntegerField(default=1)

    #Time
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CombatInstance {self.id} - Party {self.party.name} - Status {self.status}"
    
class Combatant(models.Model):
    #Link to entity (Character or Monster) and battle instance
    combat_instance = models.ForeignKey('battles.CombatInstance', on_delete=models.CASCADE, related_name='combatants')
    
    #GeneericForeignKey-like fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    objects_id = models.CharField(max_length=100) #ID of the entity in its respective table
    entity = GenericForeignKey('content_type', 'objects_id')

    is_player = models.BooleanField(default=True) #True if character, False if monster/boss

    #Temporary stats for combat
    current_hp = models.IntegerField()
    current_mp = models.IntegerField()

    #Position in turn
    position =models.PositiveIntegerField()

    class Meta:
        unique_together = ('combat_instance', 'position') #Ensure unique position per combat instance
        ordering = ['position']
    def __str__(self):
        return f"Combatant {self.content_type} {self.objects_id} in CombatInstance {self.combat_instance.id}"

class ActiveEffect(models.Model):
    """
    Active effect on a combatant
    """
    id = models.AutoField(primary_key=True)
    # Link to combat
    combat_instance = models.ForeignKey('battles.CombatInstance', on_delete=models.CASCADE, related_name='active_effects')
    target = models.ForeignKey('battles.Combatant', on_delete=models.CASCADE, related_name='active_effects')
    effect_template = models.ForeignKey('abilities.EffectTemplate', on_delete=models.CASCADE)
    remaining_turns = models.IntegerField() #Number of turns the effect will last
    current_stacks = models.IntegerField(default=1) #Current stacks of the effect, if applicable
    caster = models.ForeignKey('battles.Combatant', null=True, blank=True, on_delete=models.SET_NULL, related_name='casted_effects') #Combatant who applied the effect
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Active Effect"
        verbose_name_plural = "Active Effects"
        ordering = ['-created_at']

    def __str__(self):
        return f"Effect {self.effect_template.name} on {self.target} ({self.remaining_turns} turns left)"
    
