from rest_framework import serializers
from .models import NormalDungeonTemplate, BossDungeonTemplate, Region, Location, DungeonClearLog

class DungeonLocationField(serializers.Field):
    """Where a dungeon is, for display: {id, name, region: {id, name}} or null."""

    def __init__(self, **kwargs):
        super().__init__(read_only=True, **kwargs)

    def to_representation(self, location):
        # DRF returns null for a missing location without calling this.
        return {
            'id': location.id,
            'name': location.name,
            'region': {'id': location.region_id, 'name': location.region.name},
        }


class NormalDungeonSerializer(serializers.ModelSerializer):
    location = DungeonLocationField()

    class Meta:
        model = NormalDungeonTemplate
        fields = ['id', 'name', 'description', 'location', 'required_level', 'stamina_cost', 'exp_reward', 'lumis_reward']


class BossDungeonSerializer(serializers.ModelSerializer):
    location = DungeonLocationField()

    class Meta:
        model = BossDungeonTemplate
        fields = ['id', 'name', 'description', 'location', 'required_level', 'max_party_size', 'time_type', 'exp_reward', 'lumis_reward']


class DungeonSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    required_level = serializers.IntegerField()


class LocationSerializer(serializers.ModelSerializer):
    """A named place and the dungeons found there; no gameplay of its own."""
    region_id = serializers.IntegerField(read_only=True)
    normal_dungeons = DungeonSummarySerializer(many=True, read_only=True)
    boss_dungeons = DungeonSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Location
        fields = ['id', 'name', 'description', 'region_id', 'order', 'normal_dungeons', 'boss_dungeons']
        read_only_fields = fields


class RegionSerializer(serializers.ModelSerializer):
    locations = LocationSerializer(many=True, read_only=True)

    class Meta:
        model = Region
        fields = ['id', 'name', 'description', 'order', 'locations']
        read_only_fields = fields
