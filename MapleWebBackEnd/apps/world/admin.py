from django.contrib import admin
from .models import (
    ExperienceTable, EnemyTemplate, LootTable,
    NormalDungeonTemplate, BossDungeonTemplate,
    Region, Location, DungeonClearLog
)

# ===================================================================
# SECTION: CORE GAME DATA
# ===================================================================

@admin.register(ExperienceTable)
class ExperienceTableAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý bảng kinh nghiệm theo cấp độ.
    """
    list_display = ('level', 'required_exp')
    search_fields = ('level',)
    ordering = ('level',)


class LootTableInline(admin.TabularInline):
    """
    Quản lý bảng vật phẩm rơi ra (Loot Table) ngay trên trang EnemyTemplate.
    """
    model = LootTable
    extra = 1
    autocomplete_fields = ['item_template']
    verbose_name_plural = "Loot Table (Bảng vật phẩm rơi ra)"
    fields = ('item_template', 'base_drop_rate', 'min_quantity', 'max_quantity', 'drop_type')

class EnemySkillInline(admin.TabularInline):
    from .models import EnemySkill
    model = EnemySkill
    extra = 1
    autocomplete_fields = ['skill_template']
    verbose_name_plural = "Enemy Skills (Kỹ năng của Quái vật)"
    fields = ('skill_template', 'initial_cd', 'priority_index')


@admin.register(EnemyTemplate)
class EnemyTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chính cho các Mẫu Kẻ địch.
    """
    list_display = ('name', 'level', 'is_boss', 'base_hp', 'base_att', 'exp_reward')
    list_filter = ('is_boss', 'level')
    search_fields = ('name',)
    filter_horizontal = ()
    readonly_fields = ('id',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'level', 'is_boss')
        }),
        ('Combat Stats', {
            'fields': ('base_hp', 'base_mp', 'base_att')
        }),
        ('Rewards', {
            'fields': ('exp_reward', ('lumis_reward_min', 'lumis_reward_max'))
        }),
    )
    
    inlines = [EnemySkillInline, LootTableInline]


# ===================================================================
# SECTION: DUNGEON TEMPLATES
# ===================================================================

from .models import NormalStageEnemy, BossStageEnemy

class NormalStageEnemyInline(admin.TabularInline):
    model = NormalStageEnemy
    extra = 1
    autocomplete_fields = ['enemy']
    verbose_name_plural = "Enemies in this Stage (Max total count: 6)"

class BossStageEnemyInline(admin.TabularInline):
    model = BossStageEnemy
    extra = 1
    autocomplete_fields = ['enemy']
    verbose_name_plural = "Enemies in this Stage (Max total count: 6)"

@admin.register(NormalDungeonTemplate)
class NormalDungeonTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý cho các Mẫu Dungeon thông thường.
    """
    list_display = ('name', 'required_level', 'stamina_cost', 'exp_reward')
    search_fields = ('name',)
    readonly_fields = ('id',)
    inlines = [NormalStageEnemyInline]
    
    fieldsets = (
        ('Dungeon Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements & Cost', {
            'fields': ('required_level', 'stamina_cost')
        }),
        ('Completion Rewards', {
            'fields': ('exp_reward', 'lumis_reward')
        }),
    )


@admin.register(BossDungeonTemplate)
class BossDungeonTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý cho các Mẫu Dungeon Boss.
    """
    list_display = ('name', 'required_level', 'time_type', 'max_party_size')
    list_filter = ('time_type',)
    search_fields = ('name',)
    readonly_fields = ('id',)
    inlines = [BossStageEnemyInline]
    
    fieldsets = (
        ('Dungeon Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements & Rules', {
            'fields': ('required_level', 'time_type', 'max_party_size')
        }),
        ('Completion Rewards', {
            'fields': ('exp_reward', 'lumis_reward')
        }),
    )


# ===================================================================
# SECTION: WORLD MAP
# ===================================================================

class LocationInline(admin.TabularInline):
    model = Location
    extra = 1
    fields = ('name', 'required_level', 'normal_dungeon', 'boss_dungeon', 'has_shop', 'order')
    autocomplete_fields = ['normal_dungeon', 'boss_dungeon']


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'required_level', 'order', 'get_location_count')
    search_fields = ('name',)
    ordering = ('order',)
    inlines = [LocationInline]

    @admin.display(description='Locations')
    def get_location_count(self, obj):
        return obj.locations.count()


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'required_level', 'has_shop')
    list_filter = ('region', 'has_shop')
    search_fields = ('name', 'region__name')
    autocomplete_fields = ['region', 'normal_dungeon', 'boss_dungeon']
    filter_horizontal = ('field_enemies',)
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'region', 'required_level', 'order')
        }),
        ('Dungeon Links', {
            'fields': ('normal_dungeon', 'boss_dungeon')
        }),
        ('Field Content', {
            'fields': ('field_enemies', 'has_shop')
        }),
    )


@admin.register(DungeonClearLog)
class DungeonClearLogAdmin(admin.ModelAdmin):
    list_display = ('character', 'dungeon', 'cleared_at')
    list_filter = ('dungeon',)
    search_fields = ('character__name', 'dungeon__name')
    readonly_fields = ('cleared_at',)