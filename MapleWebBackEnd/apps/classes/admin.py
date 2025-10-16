from django.contrib import admin
from .models import CharacterClass, Job


@admin.register(CharacterClass)
class CharacterClassAdmin(admin.ModelAdmin):
    """Admin interface for CharacterClass model"""
    
    list_display = ('name', 'str_ratio', 'agi_ratio', 'int_ratio', 
                   'hp_growth', 'mp_growth')
    search_fields = ('name',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name',)
        }),
        ('Attack Ratios', {
            'fields': (('str_ratio', 'agi_ratio', 'int_ratio'),),
            'description': 'Stat needed to increase 1 attack'
        }),
        ('Growth Rates', {
            'fields': (('hp_growth', 'mp_growth'),
                      ('str_growth', 'agi_growth', 'int_growth')),
            'description': 'Stat increase per level up'
        }),
    )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin interface for Job model"""
    
    list_display = ('name', 'character_class')
    list_filter = ('character_class',)
    search_fields = ('name', 'character_class__name')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'character_class')
        }),
    )
    
    autocomplete_fields = ['character_class']
