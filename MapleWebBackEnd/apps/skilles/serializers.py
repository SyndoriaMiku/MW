from rest_framework import serializers
from .models import SkillTemplate, SkillLevelConfig, EffectTemplate


class EffectTemplateBriefSerializer(serializers.ModelSerializer):
    """Lightweight serializer for EffectTemplate used inside SkillTemplate."""
    class Meta:
        model = EffectTemplate
        fields = [
            'id', 'name', 'description', 'duration_turns', 'stacking_rule',
            'flat_hp_change', 'percent_hp_change',
            'flat_mp_change', 'percent_mp_change',
            'flat_att_change', 'percent_att_change',
            'flat_str_change', 'percent_str_change',
            'flat_agi_change', 'percent_agi_change',
            'flat_int_change', 'percent_int_change',
            'hp_change_per_turn', 'mp_change_per_turn', 'damage_power_ratio_per_turn',
            'shields_points', 'final_damage_modifier',
            'damage_taken_modifier', 'damage_dealt_modifier',
            'exp_rate_change', 'drop_rate_change', 'lumis_rate_change',
            'dispellable',
        ]


class SkillLevelConfigSerializer(serializers.ModelSerializer):
    """Represents one level milestone of a skill."""
    requires_materials = serializers.BooleanField(read_only=True)

    class Meta:
        model = SkillLevelConfig
        fields = [
            'skill_level', 'required_char_level',
            'damage_multiplier', 'required_materials', 'requires_materials',
        ]


class SkillTemplateSerializer(serializers.ModelSerializer):
    """Full skill detail including all level configs and effect template."""
    level_configs = SkillLevelConfigSerializer(many=True, read_only=True)
    applies_effect = EffectTemplateBriefSerializer(read_only=True)
    formatted_description = serializers.CharField(read_only=True)
    job_name = serializers.SerializerMethodField()

    class Meta:
        model = SkillTemplate
        fields = [
            'id', 'name', 'description', 'formatted_description',
            'icon_key', 'visual_key', 'availability',
            'job', 'job_name', 'required_level',
            'mp_cost', 'cooldown',
            'target_type', 'effect_type', 'is_basic_attack',
            'base_power', 'power_ratio',
            'applies_effect', 'level_configs',
        ]

    def get_job_name(self, obj):
        return obj.job.name if obj.job else None


class SkillTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing skills (no nested configs)."""
    job_name = serializers.SerializerMethodField()

    class Meta:
        model = SkillTemplate
        fields = [
            'id', 'name', 'description',
            'icon_key', 'visual_key', 'availability',
            'job', 'job_name', 'required_level',
            'mp_cost', 'cooldown',
            'target_type', 'effect_type', 'is_basic_attack',
            'base_power', 'power_ratio',
        ]

    def get_job_name(self, obj):
        return obj.job.name if obj.job else None
