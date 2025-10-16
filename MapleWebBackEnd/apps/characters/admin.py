from django.contrib import admin
from .models import Character, Equipment, CharacterSkill


class EquipmentInline(admin.StackedInline):
    """Inline for equipment"""
    model = Equipment
    can_delete = False
    verbose_name_plural = 'Equipment'
    
    fieldsets = (
        ('Accessories', {
            'fields': (('pendant', 'earring', 'belt'), 'rings')
        }),
        ('Cosmetics', {
            'fields': (('face', 'eye'),)
        }),
        ('Armor', {
            'fields': (('hat', 'top', 'bottom'), ('shoes', 'cape', 'gloves', 'shoulder'))
        }),
        ('Weapon', {
            'fields': ('weapon',)
        }),
    )
    
    autocomplete_fields = ['pendant', 'earring', 'belt', 'face', 'eye', 'hat', 'top', 'bottom', 
                          'shoes', 'cape', 'gloves', 'shoulder', 'weapon', 'rings']


class CharacterSkillInline(admin.TabularInline):
    """Inline for character skills"""
    model = CharacterSkill
    extra = 0
    fields = ('skill_template', 'level')
    autocomplete_fields = ['skill_template']


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    """Admin interface for Character model"""
    
    list_display = ('id', 'name', 'owner', 'level', 'character_class', 'job', 
                   'current_stamina', 'max_stamina')
    list_filter = ('character_class', 'job', 'level')
    search_fields = ('name', 'id', 'owner__username')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'owner', 'character_class', 'job')
        }),
        ('Base Stats', {
            'fields': (('base_hp', 'base_mp', 'base_att'), 
                      ('base_str', 'base_agi', 'base_int'),
                      'drop_rate')
        }),
        ('Leveling', {
            'fields': (('level', 'current_exp'),)
        }),
        ('Stamina System', {
            'fields': (('current_stamina', 'max_stamina'), 'last_stamina_update'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('id', 'last_stamina_update')
    
    autocomplete_fields = ['owner', 'character_class', 'job']
    
    inlines = [EquipmentInline, CharacterSkillInline]
    
    actions = ['restore_full_stamina']
    
    def restore_full_stamina(self, request, queryset):
        """Restore stamina to max for selected characters"""
        for character in queryset:
            character.current_stamina = character.max_stamina
            character.save()
        self.message_user(request, f"{queryset.count()} characters' stamina restored.")
    restore_full_stamina.short_description = "Restore full stamina"


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    """Admin interface for Equipment model"""
    
    list_display = ('character', 'weapon', 'hat', 'top', 'bottom', 'shoes')
    search_fields = ('character__name', 'character__id')
    
    fieldsets = (
        ('Character', {
            'fields': ('character',)
        }),
        ('Accessories', {
            'fields': (('pendant', 'earring', 'belt'), 'rings')
        }),
        ('Cosmetics', {
            'fields': (('face', 'eye'),)
        }),
        ('Armor', {
            'fields': (('hat', 'top', 'bottom'), ('shoes', 'cape', 'gloves', 'shoulder'))
        }),
        ('Weapon', {
            'fields': ('weapon',)
        }),
    )
    
    autocomplete_fields = ['character', 'pendant', 'earring', 'belt', 'face', 'eye', 
                          'hat', 'top', 'bottom', 'shoes', 'cape', 'gloves', 
                          'shoulder', 'weapon', 'rings']


@admin.register(CharacterSkill)
class CharacterSkillAdmin(admin.ModelAdmin):
    """Admin interface for CharacterSkill model"""
    
    list_display = ('character', 'skill_template', 'level')
    list_filter = ('level',)
    search_fields = ('character__name', 'skill_template__name')
    
    fieldsets = (
        (None, {
            'fields': ('character', 'skill_template', 'level')
        }),
    )
    
    autocomplete_fields = ['character', 'skill_template']
