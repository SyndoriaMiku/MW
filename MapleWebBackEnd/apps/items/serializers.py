from rest_framework import serializers
from .models import ItemSet, ItemSetEffect, ItemTemplate


class ItemSetEffectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemSetEffect
        fields = [
            'id', 'required_count', 'hp_boost', 'mp_boost', 'att_boost',
            'str_boost', 'agi_boost', 'int_boost', 'all_stats_boost',
        ]


class ItemSetMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemTemplate
        fields = ['id', 'name', 'item_type', 'icon_key', 'visual_key']


class ItemSetSerializer(serializers.ModelSerializer):
    effects = ItemSetEffectSerializer(many=True, read_only=True)
    items = ItemSetMemberSerializer(many=True, read_only=True)

    class Meta:
        model = ItemSet
        fields = ['id', 'name', 'description', 'items', 'effects']

class ItemTemplateSerializer(serializers.ModelSerializer):
    item_sets = ItemSetSerializer(many=True, read_only=True)

    class Meta:
        model = ItemTemplate
        fields = '__all__'


class LumenAscendRequestSerializer(serializers.Serializer):
    inventory_item_id = serializers.IntegerField(min_value=1)


class AuroraRevealRequestSerializer(serializers.Serializer):
    inventory_item_id = serializers.IntegerField(min_value=1)


class AuroraModifyRequestSerializer(serializers.Serializer):
    target_item_id = serializers.IntegerField(min_value=1)
    modifier_item_id = serializers.IntegerField(min_value=1, required=False)
    use_lumis = serializers.BooleanField(default=False)
    target_line_index = serializers.IntegerField(min_value=0, required=False)

    def validate(self, attrs):
        modifier_item_id = attrs.get('modifier_item_id')
        use_lumis = attrs.get('use_lumis', False)
        if bool(modifier_item_id) == bool(use_lumis):
            raise serializers.ValidationError(
                'Provide exactly one of modifier_item_id or use_lumis=true.'
            )
        return attrs


class AuroraConfirmRequestSerializer(serializers.Serializer):
    inventory_item_id = serializers.IntegerField(min_value=1)
    action = serializers.ChoiceField(
        choices=['keep_old', 'take_new', 'select_specific']
    )
    selected_temp_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        required=False,
    )

    def validate(self, attrs):
        if attrs['action'] == 'select_specific' and 'selected_temp_ids' not in attrs:
            raise serializers.ValidationError({
                'selected_temp_ids': 'This field is required for select_specific.'
            })
        return attrs
