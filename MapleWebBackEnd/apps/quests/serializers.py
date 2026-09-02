from rest_framework import serializers
from .models import QuestTemplate, QuestObjective, QuestReward, CharacterQuest, CharacterQuestObjective


class QuestObjectiveSerializer(serializers.ModelSerializer):
    enemy_name = serializers.CharField(source='enemy_to_defeat.name', read_only=True, default=None)
    item_name = serializers.CharField(source='item_to_collect.name', read_only=True, default=None)
    dungeon_name = serializers.CharField(source='dungeon_to_clear.name', read_only=True, default=None)
    boss_dungeon_name = serializers.CharField(source='boss_dungeon_to_clear.name', read_only=True, default=None)
    
    class Meta:
        model = QuestObjective
        fields = [
            'id', 'enemy_to_defeat', 'enemy_name', 'defeat_count',
            'item_to_collect', 'item_name', 'collect_count',
            'dungeon_to_clear', 'dungeon_name', 'clear_count',
            'boss_dungeon_to_clear', 'boss_dungeon_name', 'boss_clear_count',
        ]


class QuestRewardSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item_template.name', read_only=True)
    
    class Meta:
        model = QuestReward
        fields = ['id', 'item_template', 'item_name', 'quantity']


class QuestTemplateSerializer(serializers.ModelSerializer):
    objectives = QuestObjectiveSerializer(many=True, read_only=True)
    rewards = QuestRewardSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuestTemplate
        fields = [
            'id', 'name', 'description', 'quest_type',
            'required_level', 'exp_reward', 'lumis_reward',
            'objectives', 'rewards'
        ]


class ObjectiveProgressSerializer(serializers.ModelSerializer):
    objective = QuestObjectiveSerializer(read_only=True)
    
    class Meta:
        model = CharacterQuestObjective
        fields = ['id', 'objective', 'current_count', 'is_completed']


class CharacterQuestSerializer(serializers.ModelSerializer):
    quest = QuestTemplateSerializer(read_only=True)
    objective_progress = ObjectiveProgressSerializer(many=True, read_only=True)
    
    class Meta:
        model = CharacterQuest
        fields = [
            'id', 'quest', 'status', 'started_at', 'completed_at',
            'last_reset_at', 'objective_progress'
        ]
