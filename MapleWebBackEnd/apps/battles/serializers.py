from rest_framework import serializers
from .models import CombatInstance, Combatant, ActiveEffect


class ActiveEffectSerializer(serializers.ModelSerializer):
    effect_name = serializers.CharField(source='effect_template.name', read_only=True)
    
    class Meta:
        model = ActiveEffect
        fields = ['id', 'effect_name', 'remaining_turns', 'current_stacks', 'remaining_shield_points']


class CombatantSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    active_effects = ActiveEffectSerializer(many=True, read_only=True)
    max_hp = serializers.SerializerMethodField()
    max_mp = serializers.SerializerMethodField()
    
    class Meta:
        model = Combatant
        fields = [
            'id', 'name', 'is_player', 'current_hp', 'current_mp',
            'max_hp', 'max_mp', 'position', 'skill_cooldowns', 'active_effects'
        ]
    
    def get_name(self, obj):
        entity = obj.entity
        return getattr(entity, 'name', str(entity))
    
    def get_max_hp(self, obj):
        entity = obj.entity
        if obj.is_player:
            return getattr(entity, 'total_hp', getattr(entity, 'base_hp', 0))
        return getattr(entity, 'base_hp', 0)
    
    def get_max_mp(self, obj):
        entity = obj.entity
        if obj.is_player:
            return getattr(entity, 'total_mp', getattr(entity, 'base_mp', 0))
        return getattr(entity, 'base_mp', 0)


class CombatInstanceSerializer(serializers.ModelSerializer):
    combatants = CombatantSerializer(many=True, read_only=True)
    
    class Meta:
        model = CombatInstance
        fields = [
            'id', 'status', 'turn_phase', 'turn_count',
            'current_player_position', 'combatants',
            'created_at', 'updated_at'
        ]


class StartBattleSerializer(serializers.Serializer):
    """Serializer for starting a new battle."""
    normal_dungeon_id = serializers.IntegerField(required=False, help_text="ID of the Normal Dungeon to fight")
    boss_dungeon_id = serializers.IntegerField(required=False, help_text="ID of the Boss Dungeon to fight")
    # For custom/field battles with specific enemies
    enemy_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of EnemyTemplate IDs for field battles"
    )


class PlayerActionSerializer(serializers.Serializer):
    """Serializer for player combat actions."""
    action_type = serializers.ChoiceField(choices=['ATTACK', 'SKILL'], help_text="Type of action")
    target_position = serializers.IntegerField(help_text="Position of the target combatant")
    skill_id = serializers.IntegerField(required=False, help_text="ID of the skill to use (required for SKILL action)")
