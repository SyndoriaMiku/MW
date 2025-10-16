from django.contrib import admin
from .models import CombatInstance, Combatant


class CombatantInline(admin.TabularInline):
    """Inline for Combatants"""
    model = Combatant
    extra = 0
    fields = ('entity_type', 'objects_id', 'is_player', 'current_hp', 'current_mp')
    readonly_fields = ('entity_type', 'objects_id')


@admin.register(CombatInstance)
class CombatInstanceAdmin(admin.ModelAdmin):
    """Admin interface for CombatInstance model"""
    
    list_display = ('id', 'party', 'status', 'turn_phase', 'turn_count', 
                   'created_at', 'updated_at')
    list_filter = ('status', 'turn_phase', 'created_at')
    search_fields = ('party__name', 'party__leader__name')
    
    fieldsets = (
        ('Battle Information', {
            'fields': ('party', 'status', 'turn_phase', 'turn_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['party']
    inlines = [CombatantInline]
    
    actions = ['end_battle']
    
    def end_battle(self, request, queryset):
        """End selected battles"""
        updated = queryset.update(status='COMPLETED')
        self.message_user(request, f"{updated} battles ended.")
    end_battle.short_description = "End selected battles"


@admin.register(Combatant)
class CombatantAdmin(admin.ModelAdmin):
    """Admin interface for Combatant model"""
    
    list_display = ('combat_instance', 'entity_type', 'objects_id', 
                   'is_player', 'current_hp', 'current_mp')
    list_filter = ('entity_type', 'is_player')
    search_fields = ('combat_instance__id', 'objects_id')
    
    fieldsets = (
        ('Battle Information', {
            'fields': ('combat_instance', 'entity_type', 'objects_id', 'is_player')
        }),
        ('Combat Stats', {
            'fields': (('current_hp', 'current_mp'),)
        }),
    )
    
    autocomplete_fields = ['combat_instance']
