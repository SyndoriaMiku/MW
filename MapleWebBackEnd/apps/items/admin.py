from django.contrib import admin
from .models import (
    ItemTemplate, ItemSet, ItemSetEffect,
    LumenTierProperty, AuroraProperty, LumenCostRule, AuroraLineCountConfig,
    AuroraLinePool, LumenAscendRule, LumenEvent, AuroraModifierRule, AuroraEvent
)
from .forms import LumenAscendRuleForm

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
    model = LumenAscendRule
    form = LumenAscendRuleForm
    extra = 1
    fields = ('item_types', 'lumen_level', 'hp_boost', 'mp_boost', 'att_boost', 'str_boost', 'agi_boost', 'int_boost')
    verbose_name_plural = "Stat Boost Rules (Luật cộng chỉ số)"
    ordering = ('lumen_level',)


from .forms import LumenAscendRuleForm, AuroraLinePoolForm

class AuroraLinePoolInline(admin.TabularInline):
    """Quản lý các dòng Aurora ngay trên trang Aurora Property."""
    model = AuroraLinePool
    form = AuroraLinePoolForm
    extra = 1
    fields = ('item_types', 'aurora_level', 'stat_type', 'line_type', 'value', 'weight')
    verbose_name_plural = "Aurora Line Pool (Các dòng tiềm năng)"
    ordering = ('aurora_level',)


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


@admin.action(description='Nhân bản (Duplicate) bản ghi này kèm toàn bộ Rules')
def duplicate_lumen_tier(modeladmin, request, queryset):
    for obj in queryset:
        old_id = obj.pk
        old_obj = LumenTierProperty.objects.get(pk=old_id)
        
        obj.pk = None
        obj.name = f"{obj.name} (Copy)"
        obj.save()
        
        for cost_rule in old_obj.cost_rules.all():
            cost_rule.pk = None
            cost_rule.lumen_tier = obj
            cost_rule.save()
            
        for ascend_rule in old_obj.ascend_rules.all():
            ascend_rule.pk = None
            ascend_rule.lumen_tier = obj
            ascend_rule.save()
    modeladmin.message_user(request, f"Đã nhân bản thành công {queryset.count()} bản ghi.")


@admin.action(description='Nhân bản theo Class (Tự tạo bản AGI và INT)')
def duplicate_lumen_tier_classes(modeladmin, request, queryset):
    for obj in queryset:
        old_id = obj.pk
        old_obj = LumenTierProperty.objects.get(pk=old_id)
        
        variants = [('AGI Variant', 'agi_boost'), ('INT Variant', 'int_boost')]
        
        for variant_name, stat_field in variants:
            new_obj = LumenTierProperty.objects.get(pk=old_id)
            new_obj.pk = None
            new_obj.name = f"{old_obj.name} ({variant_name})"
            new_obj.save()
            
            for cost_rule in old_obj.cost_rules.all():
                cost_rule.pk = None
                cost_rule.lumen_tier = new_obj
                cost_rule.save()
                
            for ascend_rule in old_obj.ascend_rules.all():
                main_stat_val = max(ascend_rule.str_boost, ascend_rule.agi_boost, ascend_rule.int_boost)
                
                ascend_rule.str_boost = 0
                ascend_rule.agi_boost = 0
                ascend_rule.int_boost = 0
                
                setattr(ascend_rule, stat_field, main_stat_val)
                
                ascend_rule.pk = None
                ascend_rule.lumen_tier = new_obj
                ascend_rule.save()
    modeladmin.message_user(request, f"Đã tự động tạo các bản AGI và INT cho {queryset.count()} bản ghi.")


@admin.register(LumenTierProperty)
class LumenTierPropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'max_lumen_level')
    search_fields = ('name',)
    inlines = [LumenCostRuleInline, LumenAscendRuleInline]
    actions = [duplicate_lumen_tier, duplicate_lumen_tier_classes]

    class Media:
        css = {
            'all': ('items/css/lumen_ascend_admin.css',)
        }


@admin.action(description='Nhân bản (Duplicate) bản ghi này kèm toàn bộ Pools')
def duplicate_aurora_property(modeladmin, request, queryset):
    for obj in queryset:
        old_id = obj.pk
        from .models import AuroraProperty
        old_obj = AuroraProperty.objects.get(pk=old_id)
        
        obj.pk = None
        obj.name = f"{obj.name} (Copy)"
        obj.save()
        
        for pool in old_obj.line_pools.all():
            pool.pk = None
            pool.aurora_property = obj
            pool.save()
    modeladmin.message_user(request, f"Đã nhân bản thành công {queryset.count()} bản ghi.")


@admin.register(AuroraProperty)
class AuroraPropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'max_aurora_level')
    search_fields = ('name',)
    inlines = [AuroraLinePoolInline]
    actions = [duplicate_aurora_property]

    class Media:
        css = {
            'all': ('items/css/lumen_ascend_admin.css',)
        }


@admin.register(LumenEvent)
class LumenEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'success_flat_bonus', 'heavy_failure_multiplier', 'bonus_levels', 'start_time', 'end_time')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

@admin.register(AuroraModifierRule)
class AuroraModifierRuleAdmin(admin.ModelAdmin):
    list_display = ('item_template', 'modifier_type', 'max_aurora_target', 'tier_up_chance')
    list_filter = ('modifier_type',)
    search_fields = ('item_template__name',)

@admin.register(AuroraLineCountConfig)
class AuroraLineCountConfigAdmin(admin.ModelAdmin):
    list_display = ('min_item_level', 'max_lines')
    ordering = ('-min_item_level',)
@admin.register(AuroraEvent)
class AuroraEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'tier_up_chance_multiplier', 'start_time', 'end_time')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

# ===================================================================
# SECTION: OPTIONAL RULE ADMINS (for global view)
# ===================================================================
# Đăng ký các model Rule riêng để có thể xem/lọc tất cả các rule nếu cần
# admin.site.register(LumenAscendRule)
# admin.site.register(AuroraLinePool)
# admin.site.register(LumenCostRule)
# admin.site.register(ItemSetEffect)