from rest_framework import serializers
from .models import InventoryItem, AuroraLine
from apps.characters.models import EquippedItem
from apps.items.serializers import ItemTemplateSerializer


LUMEN_STAT_FIELDS = (
    'hp_boost', 'mp_boost', 'att_boost',
    'str_boost', 'agi_boost', 'int_boost',
)

class AuroraLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuroraLine
        fields = '__all__'

class InventoryItemSerializer(serializers.ModelSerializer):
    aurora_lines = AuroraLineSerializer(many=True, read_only=True)
    template = ItemTemplateSerializer(read_only=True)
    lumen_breakdown = serializers.SerializerMethodField()

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
        fields = '__all__'

class EquippedItemSerializer(serializers.ModelSerializer):
    item = InventoryItemSerializer(read_only=True)
    
    class Meta:
        model = EquippedItem
        fields = '__all__'
