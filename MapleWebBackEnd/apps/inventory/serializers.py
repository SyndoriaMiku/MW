from rest_framework import serializers
from .models import InventoryItem, AuroraLine
from apps.characters.models import EquipmentSlotConfig, EquippedItem
from apps.items.serializers import ItemTemplateSerializer


LUMEN_STAT_FIELDS = (
    'hp_boost', 'mp_boost', 'att_boost',
    'str_boost', 'agi_boost', 'int_boost',
)

class AuroraLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuroraLine
        fields = [
            'id', 'line_index', 'stat_type', 'line_type', 'value',
            'inventory_item',
        ]
        read_only_fields = fields

class InventoryItemSerializer(serializers.ModelSerializer):
    aurora_lines = AuroraLineSerializer(many=True, read_only=True)
    template = ItemTemplateSerializer(read_only=True)
    lumen_breakdown = serializers.SerializerMethodField()
    # Lumis price of an Aurora reroll right now; null when not available.
    aurora_lumis_reroll_cost = serializers.SerializerMethodField()

    def get_aurora_lumis_reroll_cost(self, obj):
        from apps.items.models import AuroraLumisCostRule

        if not obj.template.aurora_tier_id or obj.aurora_level < 1:
            return None
        # Load the small price table once per response, not once per item.
        if '_aurora_lumis_cost_rules' not in self.context:
            self.context['_aurora_lumis_cost_rules'] = list(AuroraLumisCostRule.objects.all())
        return AuroraLumisCostRule.cost_for(obj, self.context['_aurora_lumis_cost_rules'])

    def get_lumen_breakdown(self, obj):
        tier = obj.template.lumen_tier
        total = {field: 0 for field in LUMEN_STAT_FIELDS}
        levels = []

        if tier and obj.lumen_ascend_level > 0:
            rules_by_level = {
                rule.lumen_level: rule
                for rule in tier.ascend_rules.all()
                if obj.template.item_type in rule.item_types
            }
            for level in range(1, obj.lumen_ascend_level + 1):
                rule = rules_by_level.get(level)
                if not rule:
                    continue
                stats = {field: getattr(rule, field) for field in LUMEN_STAT_FIELDS}
                levels.append({'level': level, 'stats': stats})
                for field, value in stats.items():
                    total[field] += value

        return {
            'current_level': obj.lumen_ascend_level,
            'tier': None if tier is None else {
                'id': tier.id,
                'name': tier.name,
                'tier': tier.tier,
                'max_level': tier.max_lumen_level,
            },
            'levels': levels,
            'total': total,
        }

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'aurora_lines', 'template', 'lumen_breakdown', 'aurora_lumis_reroll_cost',
            'lumen_ascend_level', 'aurora_level', 'quantity', 'is_untrade',
            'expired_at', 'is_destroyed', 'owner',
        ]
        read_only_fields = fields

class EquippedItemSerializer(serializers.ModelSerializer):
    item = InventoryItemSerializer(read_only=True)
    
    class Meta:
        model = EquippedItem
        fields = [
            'id', 'item', 'slot_index', 'character', 'slot',
        ]
        read_only_fields = fields


class EquipmentSlotConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentSlotConfig
        fields = ['id', 'slot_type', 'display_name', 'max_count', 'allowed_item_types', 'order']
        read_only_fields = fields
