from django.contrib import admin
from .models import QuestTemplate, QuestObjective, QuestReward

# ===================================================================
# INLINE ADMINS
# ===================================================================

class QuestObjectiveInline(admin.TabularInline):
    model = QuestObjective
    extra = 1
    fields = ('enemy_to_defeat', 'defeat_count', 'item_to_collect', 'collect_count', 'dungeon_to_clear', 'clear_count')
    autocomplete_fields = ('enemy_to_defeat', 'item_to_collect', 'dungeon_to_clear')

class QuestRewardInline(admin.TabularInline):
    model = QuestReward
    extra = 1
    fields = ('item_template', 'quantity')
    autocomplete_fields = ('item_template',)

# ===================================================================
# MODEL ADMINS
# ===================================================================

@admin.register(QuestTemplate)
class QuestTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'quest_type', 'required_level', 'exp_reward', 'lumis_reward')
    list_filter = ('quest_type', 'required_level')
    search_fields = ('id', 'name', 'description')
    readonly_fields = ('id',)
    filter_horizontal = ('prerequisite_quests',)
    inlines = [QuestObjectiveInline, QuestRewardInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'quest_type')
        }),
        ('Requirements', {
            'fields': ('required_level', 'prerequisite_quests'),
            'description': 'Prerequisites to start this quest'
        }),
        ('Rewards', {
            'fields': ('exp_reward', 'lumis_reward'),
            'description': 'Base rewards for completing the quest (item rewards configured in Quest Rewards section below)'
        }),
    )
    
    actions = ['duplicate_quests']
    
    def duplicate_quests(self, request, queryset):
        """Duplicate selected quests"""
        count = 0
        for quest in queryset:
            objectives = list(quest.objectives.all())
            rewards = list(quest.rewards.all())
            prerequisite_quests = list(quest.prerequisite_quests.all())
            
            quest.pk = None
            quest.id = None
            quest.name = f"{quest.name} (Copy)"
            quest.save()
            
            # Re-add M2M relationships
            quest.prerequisite_quests.set(prerequisite_quests)
            
            # Re-create objectives
            for objective in objectives:
                objective.pk = None
                objective.quest = quest
                objective.save()
            
            # Re-create rewards
            for reward in rewards:
                reward.pk = None
                reward.quest = quest
                reward.save()
            
            count += 1
        
        self.message_user(request, f'Successfully duplicated {count} quests.')
    duplicate_quests.short_description = 'Duplicate selected quests'

@admin.register(QuestObjective)
class QuestObjectiveAdmin(admin.ModelAdmin):
    list_display = ('quest', 'get_objective_type', 'get_target', 'get_count')
    list_filter = ('quest__quest_type',)
    search_fields = ('quest__name',)
    autocomplete_fields = ('quest', 'enemy_to_defeat', 'item_to_collect', 'dungeon_to_clear')
    
    fieldsets = (
        ('Quest', {
            'fields': ('quest',)
        }),
        ('Enemy Objective', {
            'fields': ('enemy_to_defeat', 'defeat_count'),
            'description': 'Configure if objective is to defeat enemies'
        }),
        ('Collection Objective', {
            'fields': ('item_to_collect', 'collect_count'),
            'description': 'Configure if objective is to collect items'
        }),
        ('Dungeon Objective', {
            'fields': ('dungeon_to_clear', 'clear_count'),
            'description': 'Configure if objective is to clear dungeons'
        }),
    )
    
    def get_objective_type(self, obj):
        if obj.enemy_to_defeat:
            return 'Defeat Enemy'
        elif obj.item_to_collect:
            return 'Collect Item'
        elif obj.dungeon_to_clear:
            return 'Clear Dungeon'
        return 'Unknown'
    get_objective_type.short_description = 'Type'
    
    def get_target(self, obj):
        if obj.enemy_to_defeat:
            return obj.enemy_to_defeat.name
        elif obj.item_to_collect:
            return obj.item_to_collect.name
        elif obj.dungeon_to_clear:
            return obj.dungeon_to_clear.name
        return 'N/A'
    get_target.short_description = 'Target'
    
    def get_count(self, obj):
        if obj.enemy_to_defeat:
            return obj.defeat_count
        elif obj.item_to_collect:
            return obj.collect_count
        elif obj.dungeon_to_clear:
            return obj.clear_count
        return 0
    get_count.short_description = 'Count'

@admin.register(QuestReward)
class QuestRewardAdmin(admin.ModelAdmin):
    list_display = ('quest', 'item_template', 'quantity')
    list_filter = ('quest__quest_type',)
    search_fields = ('quest__name', 'item_template__name')
    autocomplete_fields = ('quest', 'item_template')
    
    fieldsets = (
        ('Reward Details', {
            'fields': ('quest', 'item_template', 'quantity')
        }),
    )
