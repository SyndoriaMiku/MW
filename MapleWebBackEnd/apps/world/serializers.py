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
