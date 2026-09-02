from rest_framework import serializers
from .models import Character

class CharacterSerializer(serializers.ModelSerializer):
    total_str = serializers.IntegerField(read_only=True)
    total_agi = serializers.IntegerField(read_only=True)
    total_int = serializers.IntegerField(read_only=True)
    total_hp = serializers.IntegerField(read_only=True)
    total_mp = serializers.IntegerField(read_only=True)
    total_att = serializers.IntegerField(read_only=True)
    total_damage = serializers.IntegerField(read_only=True)
    total_final_damage = serializers.FloatField(read_only=True)

    class Meta:
        model = Character
        fields = [
            'id', 'name', 'current_location', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'character_class', 'job',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update',
            'total_str', 'total_agi', 'total_int', 'total_hp', 'total_mp', 'total_att',
            'total_damage', 'total_final_damage'
        ]
        read_only_fields = [
            'id', 'current_location', 'base_hp', 'base_mp', 'base_att',
            'base_str', 'base_agi', 'base_int', 'drop_rate', 'job',
            'level', 'current_exp', 'max_stamina', 'current_stamina', 'last_stamina_update'
        ]

    def to_representation(self, instance):
        instance.update_stamina()
        return super().to_representation(instance)
