from django.contrib import admin
from .models import SkillTemplate, SpecialEffectTag, EffectTemplate


@admin.register(SkillTemplate)
class SkillTemplateAdmin(admin.ModelAdmin):
    """Admin interface for SkillTemplate model"""
    
    list_display = ('name', 'job', 'required_level', 'mp_cost', 'cooldown', 
                   'target_type', 'effect_type', 'base_power')
    list_filter = ('job', 'target_type', 'effect_type', 'required_level')
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Requirements', {
            'fields': (('job', 'required_level'),)
        }),
        ('Attributes', {
            'fields': (('mp_cost', 'cooldown'),)
        }),
        ('Skill Type', {
            'fields': (('target_type', 'effect_type'),)
        }),
        ('Power', {
            'fields': (('base_power', 'power_ratio'),)
        }),
        ('Effects', {
            'fields': ('applies_effect',),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['job', 'applies_effect']


@admin.register(SpecialEffectTag)
class SpecialEffectTagAdmin(admin.ModelAdmin):
    """Admin interface for SpecialEffectTag model"""
    
    list_display = ('id', 'name')
    search_fields = ('id', 'name', 'description')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'description')
        }),
    )


@admin.register(EffectTemplate)
class EffectTemplateAdmin(admin.ModelAdmin):
    """Admin interface for EffectTemplate model"""
    
    list_display = ('name', 'duration_turns', 'stacking_rule', 'dispellable', 
                   'has_stat_changes', 'has_per_turn_effects')
    list_filter = ('stacking_rule', 'dispellable', 'duration_turns')
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'icon')
        }),
        ('Duration & Stacking', {
            'fields': (('duration_turns', 'stacking_rule'), 'dispellable')
        }),
        ('Flat Stat Changes', {
            'fields': (('flat_hp_change', 'flat_mp_change', 'flat_att_change'),
                      ('flat_str_change', 'flat_agi_change', 'flat_int_change')),
            'classes': ('collapse',)
        }),
        ('Percent Stat Changes', {
            'fields': (('percent_hp_change', 'percent_mp_change', 'percent_att_change'),
                      ('percent_str_change', 'percent_agi_change', 'percent_int_change')),
            'classes': ('collapse',)
        }),
        ('Rate Changes', {
            'fields': (('drop_rate_change', 'exp_rate_change'),),
            'classes': ('collapse',)
        }),
        ('Special Properties', {
            'fields': (('shields_points', 'cooldown_reduction'),),
            'classes': ('collapse',)
        }),
        ('Per Turn Effects', {
            'fields': (('hp_change_per_turn', 'mp_change_per_turn'),),
            'classes': ('collapse',)
        }),
        ('Damage & Healing Modifiers', {
            'fields': (('damage_taken_modifier', 'damage_dealt_modifier'),
                      ('health_received_modifier', 'mana_received_modifier'),
                      ('health_dealt_modifier', 'mana_dealt_modifier')),
            'classes': ('collapse',)
        }),
        ('Special Effect Tags', {
            'fields': ('special_effects',),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('special_effects',)
    
    def has_stat_changes(self, obj):
        """Check if effect has stat changes"""
        return any([
            obj.flat_hp_change, obj.flat_mp_change, obj.flat_att_change,
            obj.flat_str_change, obj.flat_agi_change, obj.flat_int_change,
            obj.percent_hp_change, obj.percent_mp_change, obj.percent_att_change,
            obj.percent_str_change, obj.percent_agi_change, obj.percent_int_change
        ])
    has_stat_changes.boolean = True
    has_stat_changes.short_description = 'Has Stat Changes'
    
    def has_per_turn_effects(self, obj):
        """Check if effect has per turn effects"""
        return obj.hp_change_per_turn != 0 or obj.mp_change_per_turn != 0
    has_per_turn_effects.boolean = True
    has_per_turn_effects.short_description = 'Has Per Turn Effects'
