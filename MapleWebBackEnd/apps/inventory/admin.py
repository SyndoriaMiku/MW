from django.contrib import admin
from .models import InventoryItem, AuroraLine


class AuroraLineInline(admin.TabularInline):
    """Inline for Aurora Lines"""
    model = AuroraLine
    extra = 0
    fields = ('stat_type', 'line_type', 'value')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    """Admin interface for InventoryItem model"""
    
    list_display = ('template', 'owner', 'quantity', 'lumen_ascend_level', 
                   'aurora_level', 'is_untrade', 'expired_at')
    list_filter = ('lumen_ascend_level', 'aurora_level', 'is_untrade', 'template__item_type')
    search_fields = ('template__name', 'owner__name', 'owner__id')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('template', 'owner', 'quantity')
        }),
        ('Upgrade Levels', {
            'fields': (('lumen_ascend_level', 'aurora_level'),)
        }),
        ('Trade & Expiration', {
            'fields': ('is_untrade', 'expired_at'),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['template', 'owner']
    inlines = [AuroraLineInline]
    
    actions = ['make_tradeable', 'make_untradeable', 'remove_expiration']
    
    def make_tradeable(self, request, queryset):
        """Make selected items tradeable"""
        updated = queryset.update(is_untrade=False)
        self.message_user(request, f"{updated} items made tradeable.")
    make_tradeable.short_description = "Make selected items tradeable"
    
    def make_untradeable(self, request, queryset):
        """Make selected items untradeable"""
        updated = queryset.update(is_untrade=True)
        self.message_user(request, f"{updated} items made untradeable.")
    make_untradeable.short_description = "Make selected items untradeable"
    
    def remove_expiration(self, request, queryset):
        """Remove expiration date from selected items"""
        updated = queryset.update(expired_at=None)
        self.message_user(request, f"{updated} items expiration removed.")
    remove_expiration.short_description = "Remove expiration date"


@admin.register(AuroraLine)
class AuroraLineAdmin(admin.ModelAdmin):
    """Admin interface for AuroraLine model"""
    
    list_display = ('inventory_item', 'stat_type', 'line_type', 'value')
    list_filter = ('stat_type', 'line_type')
    search_fields = ('inventory_item__template__name', 'inventory_item__owner__name')
    
    fieldsets = (
        ('Item Information', {
            'fields': ('inventory_item',)
        }),
        ('Line Properties', {
            'fields': (('stat_type', 'line_type'), 'value')
        }),
    )
    
    autocomplete_fields = ['inventory_item']
