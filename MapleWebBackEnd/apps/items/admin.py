from django.contrib import admin
from .models import (
    ItemTemplate, ItemSet, ItemSetEffect,
    LumenTierProperty, AuroraProperty, LumenCostRule,
    AuroraLinePool, LumenAscendRule
)

# ===================================================================
# SECTION: INLINE DEFINITIONS
# ===================================================================

class ItemSetEffectInline(admin.TabularInline):
    """Quản lý các hiệu ứng của Item Set ngay trên trang Item Set."""
    model = ItemSetEffect
    extra = 1
    verbose_name_plural = "Set Effects (Hiệu ứng theo bộ)"


class LumenCostRuleInline(admin.TabularInline):
    """Quản lý luật về chi phí & tỉ lệ nâng cấp Lumen ngay trên trang Lumen Tier."""
    model = LumenCostRule
    extra = 1
    fields = ('current_level', 'lumis_cost', 'success_rate', 'failure_rate', 'heavy_failure_rate')
    verbose_name_plural = "Cost & Success Rules (Luật chi phí & tỉ lệ)"
    ordering = ('current_level',)


class LumenAscendRuleInline(admin.TabularInline):
    """Quản lý luật về chỉ số cộng thêm của Lumen ngay trên trang Lumen Tier."""
    model = LumenAscendRule
    extra = 1
    fields = ('item_type', 'lumen_level', 'hp_boost', 'mp_boost', 'att_boost', 'str_boost', 'agi_boost', 'int_boost')
    verbose_name_plural = "Stat Boost Rules (Luật cộng chỉ số)"
    ordering = ('item_type', 'lumen_level',)


class AuroraLinePoolInline(admin.TabularInline):
    """Quản lý các dòng tiềm năng Aurora ngay trên trang Aurora Property."""
    model = AuroraLinePool
    extra = 1
    fields = ('item_type', 'aurora_level', 'stat_type', 'line_type', 'value', 'weight')
    verbose_name_plural = "Aurora Line Pool (Các dòng tiềm năng)"
    ordering = ('item_type', 'aurora_level',)


# ===================================================================
# SECTION: MAIN MODEL ADMINS
# ===================================================================

@admin.register(ItemTemplate)
class ItemTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'item_type', 'minimum_level', 'is_tradeable', 'sell_price')
    list_filter = ('item_type', 'is_tradeable', 'class_restriction')
    search_fields = ('name', 'description')
    filter_horizontal = ('class_restriction', 'job_restriction')
    autocomplete_fields = ('lumen_tier', 'aurora_tier')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', ('item_type', 'weapon_type'), 'sell_price')
        }),
        ('Requirements & Restrictions', {
            'fields': ('minimum_level', 'class_restriction', 'job_restriction', ('is_tradeable', 'is_sellable'))
        }),
        ('Base Stats Boost', {
            'classes': ('collapse',),
            'fields': (
                ('hp_boost', 'mp_boost'),
                ('att_boost',),
                ('str_boost', 'agi_boost', 'int_boost'),
                ('all_stats_boost', 'drop_rate_boost')
            )
        }),
        ('Upgrade Tiers', {
            'fields': ('lumen_tier', 'aurora_tier')
        }),
    )


@admin.register(ItemSet)
class ItemSetAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    filter_horizontal = ('items',)
    inlines = [ItemSetEffectInline]


@admin.register(LumenTierProperty)
class LumenTierPropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'max_lumen_level', 'heavy_failure_level')
    search_fields = ('name',)
    inlines = [LumenCostRuleInline, LumenAscendRuleInline]


@admin.register(AuroraProperty)
class AuroraPropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'max_aurora_level')
    search_fields = ('name',)
    inlines = [AuroraLinePoolInline]


# ===================================================================
# SECTION: OPTIONAL RULE ADMINS (for global view)
# ===================================================================
# Đăng ký các model Rule riêng để có thể xem/lọc tất cả các rule nếu cần
# admin.site.register(LumenAscendRule)
# admin.site.register(AuroraLinePool)
# admin.site.register(LumenCostRule)
# admin.site.register(ItemSetEffect)