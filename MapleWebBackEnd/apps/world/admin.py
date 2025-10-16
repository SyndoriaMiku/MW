from django.contrib import admin
from .models import ExperienceTable, EnemyTemplate, LootTable, NormalDungeonTemplate, BossDungeonTemplate

# ===================================================================
# INLINE ADMINS
# ===================================================================

class LootTableInline(admin.TabularInline):
    model = LootTable
    extra = 1
    fields = ('item_template', 'base_drop_rate', 'min_quantity', 'max_quantity', 'drop_type')
    autocomplete_fields = ('item_template',)

# ===================================================================
# MODEL ADMINS
# ===================================================================

@admin.register(ExperienceTable)
class ExperienceTableAdmin(admin.ModelAdmin):
    list_display = ('level', 'required_exp', 'exp_increase')
    list_filter = ('level',)
    search_fields = ('level',)
    ordering = ('level',)
    
    fieldsets = (
        ('Level Information', {
            'fields': ('level', 'required_exp')
        }),
    )
    
    def exp_increase(self, obj):
        """Calculate exp increase from previous level"""
        if obj.level == 1:
            return 'N/A'
        try:
            prev = ExperienceTable.objects.get(level=obj.level - 1)
            increase = obj.required_exp - prev.required_exp
            return f'+{increase}'
        except ExperienceTable.DoesNotExist:
            return 'N/A'
    exp_increase.short_description = 'Increase from Prev'
    
    actions = ['generate_exp_curve']
    
    def generate_exp_curve(self, request, queryset):
        """Generate experience curve for multiple levels"""
        self.message_user(request, 'Use Django management command to generate exp curve.')
    generate_exp_curve.short_description = 'Generate EXP curve (see docs)'

@admin.register(EnemyTemplate)
class EnemyTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'level', 'is_boss', 'base_hp', 'base_att', 'exp_reward', 'lumis_range')
    list_filter = ('is_boss', 'level')
    search_fields = ('id', 'name')
    readonly_fields = ('id',)
    filter_horizontal = ('skills',)
    inlines = [LootTableInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'level', 'is_boss')
        }),
        ('Combat Stats', {
            'fields': ('base_hp', 'base_mp', 'base_att'),
            'description': 'Base combat statistics for this enemy'
        }),
        ('Skills', {
            'fields': ('skills',),
            'description': 'Skills that this enemy can use in battle',
            'classes': ('collapse',)
        }),
        ('Rewards', {
            'fields': ('exp_reward', 'lumis_reward_min', 'lumis_reward_max'),
            'description': 'Base rewards for defeating this enemy (item drops configured in Loot Tables section below)'
        }),
    )
    
    def lumis_range(self, obj):
        if obj.lumis_reward_min == obj.lumis_reward_max:
            return f'{obj.lumis_reward_min}'
        return f'{obj.lumis_reward_min} - {obj.lumis_reward_max}'
    lumis_range.short_description = 'Lumis Reward'
    
    actions = ['duplicate_enemies']
    
    def duplicate_enemies(self, request, queryset):
        """Duplicate selected enemies"""
        count = 0
        for enemy in queryset:
            skills = list(enemy.skills.all())
            loot_tables = list(enemy.loot_tables.all())
            
            enemy.pk = None
            enemy.id = None
            enemy.name = f"{enemy.name} (Copy)"
            enemy.save()
            
            # Re-add M2M relationships
            enemy.skills.set(skills)
            
            # Re-create loot tables
            for loot in loot_tables:
                loot.pk = None
                loot.enemy = enemy
                loot.save()
            
            count += 1
        
        self.message_user(request, f'Successfully duplicated {count} enemies.')
    duplicate_enemies.short_description = 'Duplicate selected enemies'

@admin.register(LootTable)
class LootTableAdmin(admin.ModelAdmin):
    list_display = ('enemy', 'item_template', 'base_drop_rate', 'quantity_range', 'drop_type')
    list_filter = ('drop_type', 'enemy__is_boss')
    search_fields = ('enemy__name', 'item_template__name')
    autocomplete_fields = ('enemy', 'item_template')
    
    fieldsets = (
        ('Loot Configuration', {
            'fields': ('enemy', 'item_template')
        }),
        ('Drop Rates', {
            'fields': ('base_drop_rate', 'drop_type'),
            'description': 'Base drop rate (0.0 to 1.0) and drop type for drop rate modifications'
        }),
        ('Quantity', {
            'fields': ('min_quantity', 'max_quantity'),
            'description': 'Quantity range when item drops'
        }),
    )
    
    def quantity_range(self, obj):
        if obj.min_quantity == obj.max_quantity:
            return f'{obj.min_quantity}'
        return f'{obj.min_quantity} - {obj.max_quantity}'
    quantity_range.short_description = 'Quantity'

@admin.register(NormalDungeonTemplate)
class NormalDungeonTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'required_level', 'stamina_cost', 'exp_reward', 'lumis_reward')
    list_filter = ('required_level', 'stamina_cost')
    search_fields = ('id', 'name', 'description')
    readonly_fields = ('id',)
    filter_horizontal = ('enemies',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements', {
            'fields': ('required_level', 'stamina_cost'),
            'description': 'Requirements to enter this dungeon'
        }),
        ('Enemies', {
            'fields': ('enemies',),
            'description': 'Enemies that appear in this dungeon'
        }),
        ('Rewards', {
            'fields': ('exp_reward', 'lumis_reward'),
            'description': 'Rewards for completing this dungeon'
        }),
    )
    
    actions = ['duplicate_dungeons']
    
    def duplicate_dungeons(self, request, queryset):
        """Duplicate selected dungeons"""
        count = 0
        for dungeon in queryset:
            enemies = list(dungeon.enemies.all())
            
            dungeon.pk = None
            dungeon.id = None
            dungeon.name = f"{dungeon.name} (Copy)"
            dungeon.save()
            
            # Re-add M2M relationships
            dungeon.enemies.set(enemies)
            
            count += 1
        
        self.message_user(request, f'Successfully duplicated {count} dungeons.')
    duplicate_dungeons.short_description = 'Duplicate selected dungeons'

@admin.register(BossDungeonTemplate)
class BossDungeonTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'required_level', 'max_party_size', 'time_type', 'exp_reward', 'lumis_reward')
    list_filter = ('time_type', 'required_level', 'max_party_size')
    search_fields = ('id', 'name', 'description')
    readonly_fields = ('id',)
    filter_horizontal = ('enemies',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements', {
            'fields': ('required_level', 'max_party_size', 'time_type'),
            'description': 'Requirements to enter this boss dungeon'
        }),
        ('Enemies', {
            'fields': ('enemies',),
            'description': 'Bosses and enemies that appear in this dungeon'
        }),
        ('Rewards', {
            'fields': ('exp_reward', 'lumis_reward'),
            'description': 'Rewards for completing this boss dungeon'
        }),
    )
    
    actions = ['duplicate_dungeons']
    
    def duplicate_dungeons(self, request, queryset):
        """Duplicate selected boss dungeons"""
        count = 0
        for dungeon in queryset:
            enemies = list(dungeon.enemies.all())
            
            dungeon.pk = None
            dungeon.id = None
            dungeon.name = f"{dungeon.name} (Copy)"
            dungeon.save()
            
            # Re-add M2M relationships
            dungeon.enemies.set(enemies)
            
            count += 1
        
        self.message_user(request, f'Successfully duplicated {count} boss dungeons.')
    duplicate_dungeons.short_description = 'Duplicate selected boss dungeons'
