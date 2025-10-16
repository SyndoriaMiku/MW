from django.contrib import admin
from .models import (ItemTemplate, ItemSet, ItemSetEffect, LumenTierProperty,
                     AuroraProperty, LumenCostRule, AuroraLinePool, LumenAscendRule)


class ItemSetEffectInline(admin.TabularInline):
    """Inline for Item Set Effects"""
    model = ItemSetEffect
    extra = 1
    fields = ('required_count', 'hp_boost', 'mp_boost', 'att_boost', 
             'str_boost', 'agi_boost', 'int_boost')


class LumenCostRuleInline(admin.TabularInline):
    """Inline for Lumen Cost Rules"""
    model = LumenCostRule
    extra = 1
    fields = ('current_level', 'lumis_cost', 'success_rate', 
             'failure_rate', 'heavy_failure_rate')


class AuroraLinePoolInline(admin.TabularInline):
    """Inline for Aurora Line Pool"""
    model = AuroraLinePool
    extra = 1
    fields = ('item_type', 'aurora_level', 'stat_type', 'line_type', 'value', 'weight')


class LumenAscendRuleInline(admin.TabularInline):
    """Inline for Lumen Ascend Rules"""
    model = LumenAscendRule
    extra = 1
    fields = ('item_type', 'lumen_level', 'hp_boost', 'mp_boost', 'att_boost',
             'str_boost', 'agi_boost', 'int_boost')


@admin.register(ItemTemplate)
class ItemTemplateAdmin(admin.ModelAdmin):
    """Admin interface for ItemTemplate model"""
    
    list_display = ('name', 'item_type', 'weapon_type', 'minimum_level', 
                   'is_tradeable', 'is_sellable', 'sell_price', 'is_stackable')
    list_filter = ('item_type', 'weapon_type', 'is_tradeable', 'is_sellable', 'minimum_level')
    search_fields = ('name', 'description')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', ('item_type', 'weapon_type'), 'minimum_level')
        }),
        ('Trading & Selling', {
            'fields': (('is_tradeable', 'is_sellable'), 'sell_price')
        }),
        ('Restrictions', {
            'fields': ('class_restriction', 'job_restriction'),
            'classes': ('collapse',)
        }),
        ('Upgrade Properties', {
            'fields': (('lumen_tier', 'aurora_tier'),),
            'classes': ('collapse',)
        }),
        ('Base Stats', {
            'fields': (('hp_boost', 'mp_boost', 'att_boost'),
                      ('str_boost', 'agi_boost', 'int_boost'),
                      ('all_stats_boost', 'drop_rate_boost')),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('class_restriction', 'job_restriction')
    autocomplete_fields = ['lumen_tier', 'aurora_tier']
    
    def is_stackable(self, obj):
        """Display if item is stackable"""
        return obj.is_stackable
    is_stackable.boolean = True
    is_stackable.short_description = 'Stackable'


@admin.register(ItemSet)
class ItemSetAdmin(admin.ModelAdmin):
    """Admin interface for ItemSet model"""
    
    list_display = ('name', 'item_count')
    search_fields = ('name', 'description')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'items')
        }),
    )
    
    filter_horizontal = ('items',)
    inlines = [ItemSetEffectInline]
    
    def item_count(self, obj):
        """Display number of items in set"""
        return obj.items.count()
    item_count.short_description = 'Items in Set'


@admin.register(ItemSetEffect)
class ItemSetEffectAdmin(admin.ModelAdmin):
    """Admin interface for ItemSetEffect model"""
    
    list_display = ('item_set', 'required_count', 'hp_boost', 'mp_boost', 
                   'att_boost', 'str_boost', 'agi_boost', 'int_boost')
    list_filter = ('required_count',)
    search_fields = ('item_set__name',)
    
    fieldsets = (
        ('Set Information', {
            'fields': ('item_set', 'required_count')
        }),
        ('Stat Bonuses', {
            'fields': (('hp_boost', 'mp_boost', 'att_boost'),
                      ('str_boost', 'agi_boost', 'int_boost'))
        }),
    )
    
    autocomplete_fields = ['item_set']


@admin.register(LumenTierProperty)
class LumenTierPropertyAdmin(admin.ModelAdmin):
    """Admin interface for LumenTierProperty model"""
    
    list_display = ('name', 'tier', 'max_lumen_level', 'heavy_failure_level')
    list_filter = ('tier',)
    search_fields = ('name',)
    ordering = ('tier',)
    
    fieldsets = (
        ('Tier Information', {
            'fields': ('name', 'tier')
        }),
        ('Level Properties', {
            'fields': ('max_lumen_level', 'heavy_failure_level')
        }),
    )
    
    inlines = [LumenCostRuleInline, LumenAscendRuleInline]


@admin.register(AuroraProperty)
class AuroraPropertyAdmin(admin.ModelAdmin):
    """Admin interface for AuroraProperty model"""
    
    list_display = ('name', 'tier', 'max_aurora_level')
    list_filter = ('tier',)
    search_fields = ('name',)
    ordering = ('tier',)
    
    fieldsets = (
        ('Aurora Information', {
            'fields': ('name', 'tier', 'max_aurora_level')
        }),
    )
    
    inlines = [AuroraLinePoolInline]


@admin.register(LumenCostRule)
class LumenCostRuleAdmin(admin.ModelAdmin):
    """Admin interface for LumenCostRule model"""
    
    list_display = ('lumen_tier', 'current_level', 'lumis_cost', 
                   'success_rate', 'failure_rate', 'heavy_failure_rate')
    list_filter = ('lumen_tier', 'current_level')
    search_fields = ('lumen_tier__name',)
    
    fieldsets = (
        ('Tier Information', {
            'fields': ('lumen_tier', 'current_level', 'lumis_cost')
        }),
        ('Success Rates', {
            'fields': ('success_rate', 'failure_rate', 'heavy_failure_rate'),
            'description': 'Rates must sum to 1.0'
        }),
    )
    
    autocomplete_fields = ['lumen_tier']


@admin.register(AuroraLinePool)
class AuroraLinePoolAdmin(admin.ModelAdmin):
    """Admin interface for AuroraLinePool model"""
    
    list_display = ('aurora_property', 'item_type', 'aurora_level', 
                   'stat_type', 'line_type', 'value', 'weight')
    list_filter = ('aurora_property', 'item_type', 'aurora_level', 'stat_type', 'line_type')
    search_fields = ('aurora_property__name',)
    
    fieldsets = (
        ('Aurora Information', {
            'fields': ('aurora_property', 'item_type', 'aurora_level')
        }),
        ('Line Properties', {
            'fields': (('stat_type', 'line_type'), ('value', 'weight'))
        }),
    )
    
    autocomplete_fields = ['aurora_property']


@admin.register(LumenAscendRule)
class LumenAscendRuleAdmin(admin.ModelAdmin):
    """Admin interface for LumenAscendRule model"""
    
    list_display = ('lumen_tier', 'item_type', 'lumen_level', 
                   'hp_boost', 'mp_boost', 'att_boost',
                   'str_boost', 'agi_boost', 'int_boost')
    list_filter = ('lumen_tier', 'item_type', 'lumen_level')
    search_fields = ('lumen_tier__name',)
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('lumen_tier', 'item_type', 'lumen_level')
        }),
        ('Stat Boosts', {
            'fields': (('hp_boost', 'mp_boost', 'att_boost'),
                      ('str_boost', 'agi_boost', 'int_boost'))
        }),
    )
    
    autocomplete_fields = ['lumen_tier']
