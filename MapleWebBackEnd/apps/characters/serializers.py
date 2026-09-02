from rest_framework import serializers
from .models import Character, CharacterSkill


class CharacterSkillSerializer(serializers.ModelSerializer):
    """Serializes a character's owned skill with its current level and next upgrade info."""
    skill_id = serializers.IntegerField(source='skill_template.id', read_only=True)
    skill_name = serializers.CharField(source='skill_template.name', read_only=True)
    description = serializers.CharField(source='skill_template.formatted_description', read_only=True)
    mp_cost = serializers.IntegerField(source='skill_template.mp_cost', read_only=True)
    cooldown = serializers.IntegerField(source='skill_template.cooldown', read_only=True)
    target_type = serializers.CharField(source='skill_template.target_type', read_only=True)
    effect_type = serializers.CharField(source='skill_template.effect_type', read_only=True)
    is_basic_attack = serializers.BooleanField(source='skill_template.is_basic_attack', read_only=True)
    damage_multiplier = serializers.SerializerMethodField()
    next_upgrade = serializers.SerializerMethodField()

    class Meta:
        model = CharacterSkill
        fields = [
            'id', 'skill_id', 'skill_name', 'description',
            'level', 'damage_multiplier', 'bonus_final_damage',
            'mp_cost', 'cooldown', 'target_type', 'effect_type', 'is_basic_attack',
            'next_upgrade',
        ]

    def get_damage_multiplier(self, obj):
        """Return the damage_multiplier for the current skill level from DB."""
        from apps.skilles.models import SkillLevelConfig
        config = SkillLevelConfig.objects.filter(
            skill=obj.skill_template, skill_level=obj.level
        ).first()
        return config.damage_multiplier if config else 1.0

    def get_next_upgrade(self, obj):
        """Return info about the next upgrade, or None if already maxed."""
        from apps.skilles.models import SkillLevelConfig
        next_config = SkillLevelConfig.objects.filter(
            skill=obj.skill_template, skill_level=obj.level + 1
        ).first()
        if not next_config:
            return None
        return {
            'skill_level': next_config.skill_level,
            'required_char_level': next_config.required_char_level,
            'damage_multiplier': next_config.damage_multiplier,
            'requires_materials': next_config.requires_materials,
            'required_materials': next_config.required_materials,
        }


class CharacterSerializer(serializers.ModelSerializer):
    total_str = serializers.IntegerField(read_only=True)
    total_agi = serializers.IntegerField(read_only=True)
    total_int = serializers.IntegerField(read_only=True)
    total_hp = serializers.IntegerField(read_only=True)
    total_mp = serializers.IntegerField(read_only=True)
    total_att = serializers.IntegerField(read_only=True)
    total_damage = serializers.IntegerField(read_only=True)
    total_final_damage = serializers.FloatField(read_only=True)
    skills = CharacterSkillSerializer(many=True, read_only=True)

    class Meta:
        model = Character
        fields = [
            'id', 'name', 'current_location', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'character_class', 'job',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update',
            'total_str', 'total_agi', 'total_int', 'total_hp', 'total_mp', 'total_att',
            'total_damage', 'total_final_damage',
            'skills',
        ]
        read_only_fields = [
            'id', 'current_location', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'job',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update',
        ]

    def to_representation(self, instance):
        instance.update_stamina()
        return super().to_representation(instance)
