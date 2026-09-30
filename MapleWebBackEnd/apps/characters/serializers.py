from django.utils import timezone
from rest_framework import serializers
from .models import Character, CharacterBuff, CharacterSkill, RateEvent


class CharacterBuffSerializer(serializers.ModelSerializer):
    """A running timed buff. Bonuses are percentage points (100 = x2)."""
    item_template_id = serializers.IntegerField(source='source_template_id', read_only=True)
    name = serializers.CharField(source='source_template.name', read_only=True)
    icon_key = serializers.CharField(source='source_template.icon_key', read_only=True)

    class Meta:
        model = CharacterBuff
        fields = [
            'id', 'item_template_id', 'name', 'icon_key',
            'exp_rate_bonus', 'lumis_rate_bonus', 'drop_rate_bonus', 'epic_drop_rate_bonus',
            'started_at', 'expires_at',
        ]


class RateEventSerializer(serializers.ModelSerializer):
    """A running server-wide rate event. Bonuses are percentage points (100 = x2)."""

    class Meta:
        model = RateEvent
        fields = [
            'id', 'name', 'description', 'start_time', 'end_time',
            'exp_rate_bonus', 'lumis_rate_bonus', 'drop_rate_bonus', 'epic_drop_rate_bonus',
        ]


class CharacterSkillSerializer(serializers.ModelSerializer):
    """Serializes a character's owned skill with its current level and next upgrade info."""
    character_skill_id = serializers.IntegerField(source='id', read_only=True)
    skill_template_id = serializers.IntegerField(source='skill_template.id', read_only=True)
    # Compatibility alias. New clients should use skill_template_id.
    skill_id = serializers.IntegerField(source='skill_template.id', read_only=True)
    skill_name = serializers.CharField(source='skill_template.name', read_only=True)
    description = serializers.CharField(source='skill_template.formatted_description', read_only=True)
    mp_cost = serializers.IntegerField(source='skill_template.mp_cost', read_only=True)
    cooldown = serializers.IntegerField(source='skill_template.cooldown', read_only=True)
    target_type = serializers.CharField(source='skill_template.target_type', read_only=True)
    effect_type = serializers.CharField(source='skill_template.effect_type', read_only=True)
    is_basic_attack = serializers.BooleanField(source='skill_template.is_basic_attack', read_only=True)
    icon_key = serializers.CharField(source='skill_template.icon_key', read_only=True)
    visual_key = serializers.CharField(source='skill_template.visual_key', read_only=True)
    damage_multiplier = serializers.SerializerMethodField()
    next_upgrade = serializers.SerializerMethodField()

    class Meta:
        model = CharacterSkill
        fields = [
            'id', 'character_skill_id', 'skill_template_id', 'skill_id',
            'skill_name', 'description',
            'level', 'damage_multiplier', 'bonus_final_damage',
            'mp_cost', 'cooldown', 'target_type', 'effect_type', 'is_basic_attack',
            'icon_key', 'visual_key',
            'next_upgrade',
        ]

    def get_damage_multiplier(self, obj):
        """Return the damage_multiplier for the current skill level from DB."""
        config = next(
            (
                config for config in obj.skill_template.level_configs.all()
                if config.skill_level == obj.level
            ),
            None,
        )
        return config.damage_multiplier if config else 1.0

    def get_next_upgrade(self, obj):
        """Return info about the next upgrade, or None if already maxed."""
        next_config = next(
            (
                config for config in obj.skill_template.level_configs.all()
                if config.skill_level == obj.level + 1
            ),
            None,
        )
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
    required_exp = serializers.SerializerMethodField()
    total_str = serializers.IntegerField(read_only=True)
    total_agi = serializers.IntegerField(read_only=True)
    total_int = serializers.IntegerField(read_only=True)
    total_hp = serializers.IntegerField(read_only=True)
    total_mp = serializers.IntegerField(read_only=True)
    total_att = serializers.IntegerField(read_only=True)
    total_damage = serializers.IntegerField(read_only=True)
    total_final_damage = serializers.FloatField(read_only=True)
    # Gain multipliers (1.0 = 100%) with equipment, buffs and events applied.
    total_exp_rate = serializers.FloatField(read_only=True)
    total_lumis_rate = serializers.FloatField(read_only=True)
    total_drop_rate = serializers.FloatField(read_only=True)
    total_epic_drop_rate = serializers.FloatField(read_only=True)
    active_buffs = serializers.SerializerMethodField()
    skills = CharacterSkillSerializer(many=True, read_only=True)

    class Meta:
        model = Character
        fields = [
            'id', 'name', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'character_class', 'job',
            'level', 'current_exp', 'required_exp',
            'max_stamina', 'current_stamina', 'last_stamina_update',
            'total_str', 'total_agi', 'total_int', 'total_hp', 'total_mp', 'total_att',
            'total_damage', 'total_final_damage',
            'total_exp_rate', 'total_lumis_rate', 'total_drop_rate', 'total_epic_drop_rate',
            'active_buffs', 'skills',
        ]
        read_only_fields = [
            'id', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update',
        ]

    def validate_name(self, value):
        # DRF already trimmed surrounding spaces; the DB constraint backs this up.
        taken = Character.objects.filter(name__iexact=value)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError('This character name is already taken.')
        return value

    def validate(self, attrs):
        job = attrs.get('job')
        character_class = attrs.get('character_class')
        if job:
            if character_class and job.character_class_id != character_class.id:
                raise serializers.ValidationError({
                    'job': 'The selected job does not belong to the selected class.'
                })
            attrs['character_class'] = job.character_class
        return attrs

    def get_active_buffs(self, obj):
        buffs = obj.buffs.filter(expires_at__gt=timezone.now()).select_related('source_template')
        return CharacterBuffSerializer(buffs, many=True).data

    def get_required_exp(self, obj):
        """EXP required to advance from the character's current level."""
        from apps.world.models import ExperienceTable

        return ExperienceTable.objects.filter(
            level=obj.level
        ).values_list('required_exp', flat=True).first()

    def to_representation(self, instance):
        instance.update_stamina()
        return super().to_representation(instance)
