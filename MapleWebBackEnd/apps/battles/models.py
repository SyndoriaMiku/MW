from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

#Create UUID
import uuid

def generate_hex_id():
    return uuid.uuid4().hex[:8] #Generate a 8-character hex id

class CombatInstance(models.Model):
    id = models.CharField(primary_key=True, max_length=8, default=generate_hex_id, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class CombatStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        VICTORY = 'victory', 'Victory'
        DEFEAT = 'defeat', 'Defeat'

    class TURN_PHASE(models.TextChoices):
        PLAYER_TURN = 'player_turn', 'Player Turn'
        MONSTER_TURN = 'monster_turn', 'Monster Turn'

    #Link to party 
    party = models.ForeignKey('party.Party', on_delete=models.CASCADE, related_name='combat_instances')
    current_player_position = models.PositiveIntegerField(default=1) #Track current player position in party for turn order
    #Link to enemy group

    #Status
    status = models.CharField(max_length=20, choices=CombatStatus.choices, default=CombatStatus.IN_PROGRESS)
    turn_phase = models.CharField(max_length=20, choices=TURN_PHASE.choices, default=TURN_PHASE.PLAYER_TURN)
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
    ENTITY_TYPE=(
        ('character', 'Character'),
        ('monster', 'Monster'),
        ('boss', 'Boss'),
    )
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE)
    objects_id = models.CharField(max_length=100) #ID of the entity in its respective table
    entity = GenericForeignKey('entity_type', 'objects_id')

    is_player = models.BooleanField(default=True) #True if character, False if monster/boss

    #Temporary stats for combat
    current_hp = models.IntegerField()
    current_mp = models.IntegerField()

    #Current stat using in combat
    current_att = models.IntegerField()
    current_str = models.IntegerField()
    current_agi = models.IntegerField()
    current_int = models.IntegerField()

    position = models.PositiveIntegerField() #Position in the turn order

    def __str__(self):
        return f"Combatant {self.entity_type} {self.objects_id} in CombatInstance {self.combat_instance.id}"
