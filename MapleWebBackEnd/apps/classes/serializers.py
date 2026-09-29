from rest_framework import serializers
from .models import CharacterClass, Job

class CharacterClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = CharacterClass
        fields = [
            'id', 'name', 'main_stat', 'hp_growth', 'mp_growth',
            'str_growth', 'agi_growth', 'int_growth',
        ]
        read_only_fields = fields

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            'id', 'name', 'main_stat_weight', 'character_class',
        ]
        read_only_fields = fields
