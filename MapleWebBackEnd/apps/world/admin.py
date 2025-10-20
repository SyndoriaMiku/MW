from django.contrib import admin
from .models import (
    ExperienceTable, EnemyTemplate, LootTable,
    NormalDungeonTemplate, BossDungeonTemplate
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


@admin.register(EnemyTemplate)
class EnemyTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chính cho các Mẫu Kẻ địch.
    """
    list_display = ('name', 'level', 'is_boss', 'base_hp', 'base_att', 'exp_reward')
    list_filter = ('is_boss', 'level')
    search_fields = ('name',)
    filter_horizontal = ('skills',)
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
        ('Abilities', {
            'fields': ('skills',)
        }),
    )
    
    inlines = [LootTableInline]


# ===================================================================
# SECTION: DUNGEON TEMPLATES
# ===================================================================

@admin.register(NormalDungeonTemplate)
class NormalDungeonTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý cho các Mẫu Dungeon thông thường.
    """
    list_display = ('name', 'required_level', 'stamina_cost', 'exp_reward')
    search_fields = ('name',)
    filter_horizontal = ('enemies',)
    readonly_fields = ('id',)
    
    fieldsets = (
        ('Dungeon Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements & Cost', {
            'fields': ('required_level', 'stamina_cost')
        }),
        ('Content', {
            'fields': ('enemies',)
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
    filter_horizontal = ('enemies',)
    readonly_fields = ('id',)
    
    fieldsets = (
        ('Dungeon Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements & Rules', {
            'fields': ('required_level', 'time_type', 'max_party_size')
        }),
        ('Content', {
            'fields': ('enemies',)
        }),
        ('Completion Rewards', {
            'fields': ('exp_reward', 'lumis_reward')
        }),
    )