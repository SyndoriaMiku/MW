from rest_framework import serializers
from .models import NormalDungeonTemplate, BossDungeonTemplate, Region, Location, DungeonClearLog

class NormalDungeonSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalDungeonTemplate
        fields = ['id', 'name', 'description', 'required_level', 'stamina_cost', 'exp_reward', 'lumis_reward']


class BossDungeonSerializer(serializers.ModelSerializer):
    class Meta:
        model = BossDungeonTemplate
        fields = ['id', 'name', 'description', 'required_level', 'max_party_size', 'time_type', 'exp_reward', 'lumis_reward']


def _reference(obj):
    return {'id': obj.id, 'name': obj.name} if obj is not None else None


class LocationSerializer(serializers.ModelSerializer):
    region_id = serializers.IntegerField(read_only=True)
    normal_dungeon = serializers.SerializerMethodField()
    boss_dungeon = serializers.SerializerMethodField()
    is_accessible = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            'id', 'name', 'description', 'region_id', 'required_level', 'order',
            'has_shop', 'normal_dungeon', 'boss_dungeon', 'is_accessible',
        ]
        read_only_fields = fields

    def get_normal_dungeon(self, obj):
        return _reference(obj.normal_dungeon)

    def get_boss_dungeon(self, obj):
        return _reference(obj.boss_dungeon)

    def get_is_accessible(self, obj):
        """Whether the requesting character meets the location and region level."""
        character = self.context.get('character')
        if character is None:
            return None
        return character.level >= max(obj.required_level, obj.region.required_level)


class RegionSerializer(serializers.ModelSerializer):
    locations = LocationSerializer(many=True, read_only=True)

    class Meta:
        model = Region
        fields = ['id', 'name', 'description', 'required_level', 'order', 'locations']
        read_only_fields = fields
