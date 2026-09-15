from rest_framework import serializers
from .models import Character, CharacterSkill

class CharacterSerializer(serializers.ModelSerializer):
    total_str = serializers.IntegerField(read_only=True)
    total_agi = serializers.IntegerField(read_only=True)
    total_int = serializers.IntegerField(read_only=True)
    total_hp = serializers.IntegerField(read_only=True)
    total_mp = serializers.IntegerField(read_only=True)
    total_att = serializers.IntegerField(read_only=True)
    total_damage = serializers.IntegerField(read_only=True)
    total_final_damage = serializers.FloatField(read_only=True)

    class Meta:
        model = Character
        fields = [
            'id', 'name', 'current_location', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'character_class', 'job',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update',
            'total_str', 'total_agi', 'total_int', 'total_hp', 'total_mp', 'total_att',
            'total_damage', 'total_final_damage'
        ]
        read_only_fields = [
            'id', 'current_location', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'job',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update'
        ]

    def to_representation(self, instance):
        instance.update_stamina()
        return super().to_representation(instance)


class CharacterSkillSerializer(serializers.ModelSerializer):
    template_id = serializers.IntegerField(source='skill_template_id', read_only=True)
    name = serializers.CharField(source='skill_template.name', read_only=True)
    description = serializers.CharField(source='skill_template.formatted_description', read_only=True)
    required_level = serializers.IntegerField(source='skill_template.required_level', read_only=True)
    mp_cost = serializers.IntegerField(source='skill_template.mp_cost', read_only=True)
    cooldown = serializers.IntegerField(source='skill_template.cooldown', read_only=True)
    target_type = serializers.CharField(source='skill_template.target_type', read_only=True)
    effect_type = serializers.CharField(source='skill_template.effect_type', read_only=True)
    is_basic_attack = serializers.BooleanField(source='skill_template.is_basic_attack', read_only=True)
    visual_key = serializers.SerializerMethodField()

    class Meta:
        model = CharacterSkill
        fields = [
            'id', 'template_id', 'name', 'description', 'level',
            'required_level', 'mp_cost', 'cooldown', 'target_type',
            'effect_type', 'is_basic_attack', 'bonus_final_damage', 'visual_key',
        ]

    def get_visual_key(self, obj):
        return getattr(obj.skill_template, 'visual_key', f"skill:{obj.skill_template_id}")
