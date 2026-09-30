from rest_framework import serializers
from .models import CombatInstance, Combatant, ActiveEffect


class ActiveEffectSerializer(serializers.ModelSerializer):
    effect_name = serializers.CharField(source='effect_template.name', read_only=True)
    effect_template_id = serializers.IntegerField(read_only=True)
    effect_kind = serializers.CharField(source='effect_template.effect_kind', read_only=True)
    dispellable = serializers.BooleanField(source='effect_template.dispellable', read_only=True)
    # Special effect tag ids, e.g. 'stun', 'silence'.
    special_effects = serializers.SerializerMethodField()

    class Meta:
        model = ActiveEffect
        fields = [
            'id', 'effect_template_id', 'effect_name', 'effect_kind', 'dispellable',
            'special_effects', 'remaining_turns', 'current_stacks', 'remaining_shield_points',
        ]

    def get_special_effects(self, obj):
        return [tag.id for tag in obj.effect_template.special_effects.all()]


class CombatantSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    entity_id = serializers.CharField(source='objects_id', read_only=True)
    entity_type = serializers.SerializerMethodField()
    visual_key = serializers.SerializerMethodField()
    is_current_actor = serializers.SerializerMethodField()
    valid_actions = serializers.SerializerMethodField()
    active_effects = ActiveEffectSerializer(many=True, read_only=True)
    max_hp = serializers.SerializerMethodField()
    max_mp = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    consumables = serializers.SerializerMethodField()
    
    class Meta:
        model = Combatant
        fields = [
            'id', 'entity_id', 'entity_type', 'name', 'visual_key', 'is_player',
            'is_current_actor', 'valid_actions', 'current_hp', 'current_mp',
            'max_hp', 'max_mp', 'position', 'skill_cooldowns', 'active_effects',
            'skills', 'consumables',
        ]
    
    def get_name(self, obj):
        entity = obj.entity
        return getattr(entity, 'name', str(entity))

    def get_entity_type(self, obj):
        return 'character' if obj.is_player else 'enemy'

    def get_visual_key(self, obj):
        return getattr(
            obj.entity,
            'visual_key',
            f'{self.get_entity_type(obj)}:{obj.objects_id}',
        )

    def get_is_current_actor(self, obj):
        combat = obj.combat_instance
        return (
            combat.status == CombatInstance.CombatStatus.IN_PROGRESS
            and combat.turn_phase == CombatInstance.TURN_PHASE.PLAYER_PHASE
            and obj.is_player
            and obj.position == combat.current_player_position
            and obj.current_hp > 0
        )

    def get_valid_actions(self, obj):
        if not self.get_is_current_actor(obj):
            return []
        actions = ['ATTACK']
        if any(skill['can_use'] and not skill['is_basic_attack'] for skill in self.get_skills(obj)):
            actions.append('SKILL')
        if any(item['can_use'] for item in self.get_consumables(obj)):
            actions.append('ITEM')
        return actions

    def get_consumables(self, obj):
        """The player's battle consumable stacks that are not reserved elsewhere."""
        if not obj.is_player:
            return []
        if hasattr(obj, '_serialized_consumables'):
            return obj._serialized_consumables

        from django.utils import timezone
        from apps.inventory.models import InventoryItem
        from apps.inventory.reservations import exclude_reserved
        from .services import BattleService

        now = timezone.now()
        is_current_actor = self.get_is_current_actor(obj)
        items = exclude_reserved(
            InventoryItem.objects.filter(
                owner_id=obj.objects_id,
                is_destroyed=False,
                quantity__gt=0,
                template__battle_consumable_rule__isnull=False,
            )
        ).select_related(
            'template__battle_consumable_rule__applies_effect'
        ).order_by('template_id', 'id')

        result = []
        for item in items:
            if item.expired_at and item.expired_at <= now:
                continue
            rule = item.template.battle_consumable_rule
            cooldown_remaining = obj.skill_cooldowns.get(
                BattleService.item_cooldown_key(item.template_id), 0
            )
            result.append({
                'inventory_item_id': item.id,
                'item_template_id': item.template_id,
                'name': item.template.name,
                'icon_key': item.template.icon_key,
                'quantity': item.quantity,
                'target_type': rule.target_type,
                'hp_restore': rule.hp_restore,
                'hp_restore_percent': rule.hp_restore_percent,
                'mp_restore': rule.mp_restore,
                'mp_restore_percent': rule.mp_restore_percent,
                'effect': rule.applies_effect.name if rule.applies_effect else None,
                'cooldown': rule.cooldown_turns,
                'cooldown_remaining': cooldown_remaining,
                'can_use': is_current_actor and cooldown_remaining <= 0,
            })
        obj._serialized_consumables = result
        return result

    def get_skills(self, obj):
        if not obj.is_player:
            return []
        if hasattr(obj, '_serialized_player_skills'):
            return obj._serialized_player_skills

        from .services import BattleService

        owned_skills = obj.entity.skills.filter(
            skill_template__availability__in=['PLAYER', 'BOTH']
        ).select_related('skill_template').prefetch_related('skill_template__level_configs')
        is_current_actor = self.get_is_current_actor(obj)
        silenced = is_current_actor and BattleService.is_silenced(obj)
        result = []
        for owned in owned_skills:
            template = owned.skill_template
            cooldown_remaining = obj.skill_cooldowns.get(str(template.id), 0)
            level_config = next(
                (
                    config for config in template.level_configs.all()
                    if config.skill_level == owned.level
                ),
                None,
            )
            result.append({
                'character_skill_id': owned.id,
                'skill_template_id': template.id,
                'name': template.name,
                'level': owned.level,
                'icon_key': template.icon_key,
                'visual_key': template.visual_key,
                'target_type': template.target_type,
                'effect_type': template.effect_type,
                'is_basic_attack': template.is_basic_attack,
                'mp_cost': template.mp_cost,
                'cooldown': template.cooldown,
                'cooldown_remaining': cooldown_remaining,
                'damage_multiplier': level_config.damage_multiplier if level_config else 1.0,
                'can_use': (
                    is_current_actor
                    and obj.current_mp >= template.mp_cost
                    and cooldown_remaining <= 0
                    and (template.is_basic_attack or not silenced)
                ),
            })
        obj._serialized_player_skills = result
        return result
    
    def get_max_hp(self, obj):
        from .services import BattleService
        return BattleService.get_max_hp(obj)

    def get_max_mp(self, obj):
        from .services import BattleService
        return BattleService.get_max_mp(obj)


class CombatInstanceSerializer(serializers.ModelSerializer):
    combatants = CombatantSerializer(many=True, read_only=True)
    encounter = serializers.SerializerMethodField()

    def get_encounter(self, obj):
        if obj.normal_dungeon_id:
            return {
                'type': 'normal_dungeon',
                'id': obj.normal_dungeon_id,
                'name': obj.normal_dungeon.name,
            }
        if obj.boss_dungeon_id:
            return {
                'type': 'boss_dungeon',
                'id': obj.boss_dungeon_id,
                'name': obj.boss_dungeon.name,
            }
        return {'type': 'custom', 'id': None, 'name': None}
    
    class Meta:
        model = CombatInstance
        fields = [
            'id', 'version', 'status', 'turn_phase', 'turn_count', 'turn_started_at',
            'current_player_position', 'encounter', 'stamina_cost_on_victory',
            'stamina_charged', 'combatants',
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
    action_type = serializers.ChoiceField(
        choices=['ATTACK', 'SKILL', 'ITEM'],
        help_text="Type of action. ITEM uses a battle consumable and ends the turn.",
    )
    target_id = serializers.IntegerField(
        required=False,
        help_text=(
            "Stable Combatant ID. Required for ATTACK and single-target skills; "
            "optional for SELF, E_AREA, A_AREA and GLOBAL skills."
        ),
    )
    target_position = serializers.IntegerField(
        required=False,
        help_text="Legacy target position; follows the same rules as target_id.",
    )
    character_skill_id = serializers.IntegerField(
        required=False,
        help_text='Owned CharacterSkill ID to use for a SKILL action.',
    )
    skill_id = serializers.IntegerField(
        required=False,
        help_text='Deprecated alias for character_skill_id.',
    )
    inventory_item_id = serializers.IntegerField(
        required=False,
        help_text="Inventory item to use for an ITEM action. target_id defaults to yourself.",
    )
    client_action_id = serializers.UUIDField(
        required=False,
        help_text=(
            "Client-generated UUID for this action. Resending the same UUID "
            "returns the stored result instead of acting again."
        ),
    )
    expected_version = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Battle version the action was built from; a mismatch returns 409.",
    )

    def validate(self, attrs):
        if (
            attrs.get('action_type') == 'ATTACK'
            and attrs.get('target_id') is None
            and attrs.get('target_position') is None
        ):
            raise serializers.ValidationError({
                'target_id': 'target_id or target_position is required.'
            })
        if attrs.get('action_type') == 'ITEM' and attrs.get('inventory_item_id') is None:
            raise serializers.ValidationError({
                'inventory_item_id': 'This field is required for ITEM actions.'
            })
        if attrs.get('action_type') == 'SKILL':
            character_skill_id = attrs.get('character_skill_id')
            legacy_skill_id = attrs.get('skill_id')
            if (
                character_skill_id is not None
                and legacy_skill_id is not None
                and character_skill_id != legacy_skill_id
            ):
                raise serializers.ValidationError({
                    'character_skill_id': 'character_skill_id and skill_id must match.'
                })
            resolved_id = character_skill_id or legacy_skill_id
            if resolved_id is None:
                raise serializers.ValidationError({
                    'character_skill_id': 'This field is required for SKILL actions.'
                })
            attrs['character_skill_id'] = resolved_id
        return attrs
