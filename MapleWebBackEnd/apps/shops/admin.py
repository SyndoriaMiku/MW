from django.contrib import admin
from .models import ShopCategory, ShopItem, SpecialShopItem, SpecialShopItemRecipe
from django.utils import timezone

# ===================================================================
# INLINE ADMINS
# ===================================================================

class ShopItemInline(admin.TabularInline):
    model = ShopItem
    extra = 1
    fields = ('item_template', 'price', 'stock', 'required_level', 'order')
    autocomplete_fields = ('item_template',)

class SpecialShopItemRecipeInline(admin.TabularInline):
    model = SpecialShopItemRecipe
    extra = 1
    fields = ('item', 'quantity')
    autocomplete_fields = ('item',)

# ===================================================================
# MODEL ADMINS
# ===================================================================

@admin.register(ShopCategory)
class ShopCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'currency_type', 'required_level', 'order', 'is_event', 'is_active', 'item_count')
    list_filter = ('currency_type', 'required_level')
    search_fields = ('id', 'name')
    readonly_fields = ('id',)
    inlines = [ShopItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'order')
        }),
        ('Currency & Requirements', {
            'fields': ('currency_type', 'required_level'),
            'description': 'Currency type used in this category and level requirement to access'
        }),
        ('Event Settings', {
            'fields': ('start_date', 'end_date'),
            'description': 'Leave both blank for permanent categories. Set both for event-limited categories.',
            'classes': ('collapse',)
        }),
    )
    
    def item_count(self, obj):
        return obj.shop_items.count()
    item_count.short_description = 'Items'
    
    def is_event(self, obj):
        return obj.is_event
    is_event.boolean = True
    is_event.short_description = 'Event'
    
    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    actions = ['activate_categories', 'deactivate_categories']
    
    def activate_categories(self, request, queryset):
        """Activate selected categories by removing end date"""
        updated = 0
        for category in queryset:
            if category.end_date and category.end_date < timezone.now():
                category.end_date = None
                category.save()
                updated += 1
        self.message_user(request, f'Successfully activated {updated} categories.')
    activate_categories.short_description = 'Activate selected categories'
    
    def deactivate_categories(self, request, queryset):
        """Deactivate selected categories by setting end date to now"""
        updated = queryset.update(end_date=timezone.now())
        self.message_user(request, f'Successfully deactivated {updated} categories.')
    deactivate_categories.short_description = 'Deactivate selected categories'

@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'item_template', 'category', 'price', 'stock', 'required_level', 'order', 'stock_status')
    list_filter = ('category__currency_type', 'category', 'required_level')
    search_fields = ('id', 'item_template__name', 'category__name')
    readonly_fields = ('id',)
    autocomplete_fields = ('category', 'item_template')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'category', 'item_template')
        }),
        ('Pricing', {
            'fields': ('price', 'stock'),
            'description': 'Price in category currency. Stock 0 = unlimited.'
        }),
        ('Requirements & Display', {
            'fields': ('required_level', 'order'),
            'description': 'Level requirement and display order in shop'
        }),
    )
    
    def stock_status(self, obj):
        if obj.stock == 0:
            return 'Unlimited'
        elif obj.stock > 100:
            return f'{obj.stock} (High)'
        elif obj.stock > 10:
            return f'{obj.stock} (Medium)'
        else:
            return f'{obj.stock} (Low)'
    stock_status.short_description = 'Stock Status'
    
    actions = ['restock_items', 'make_unlimited']
    
    def restock_items(self, request, queryset):
        """Restock selected items to 999"""
        updated = queryset.exclude(stock=0).update(stock=999)
        self.message_user(request, f'Successfully restocked {updated} items to 999.')
    restock_items.short_description = 'Restock to 999'
    
    def make_unlimited(self, request, queryset):
        """Make selected items have unlimited stock"""
        updated = queryset.update(stock=0)
        self.message_user(request, f'Successfully set {updated} items to unlimited stock.')
    make_unlimited.short_description = 'Set unlimited stock'

@admin.register(SpecialShopItem)
class SpecialShopItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'is_active', 'recipe_count')
    list_filter = ('is_active',)
    search_fields = ('id', 'item__name')
    readonly_fields = ('id',)
    autocomplete_fields = ('item',)
    inlines = [SpecialShopItemRecipeInline]
    
    fieldsets = (
        ('Special Item', {
            'fields': ('id', 'item', 'is_active')
        }),
    )
    
    def recipe_count(self, obj):
        return obj.specialshopitemrecipe_set.count()
    recipe_count.short_description = 'Recipe Items'
    
    actions = ['activate_items', 'deactivate_items']
    
    def activate_items(self, request, queryset):
        """Activate selected special items"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Successfully activated {updated} special items.')
    activate_items.short_description = 'Activate selected items'
    
    def deactivate_items(self, request, queryset):
        """Deactivate selected special items"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Successfully deactivated {updated} special items.')
    deactivate_items.short_description = 'Deactivate selected items'

@admin.register(SpecialShopItemRecipe)
class SpecialShopItemRecipeAdmin(admin.ModelAdmin):
    list_display = ('recipe', 'item', 'quantity', 'get_target_item')
    list_filter = ('recipe__is_active',)
    search_fields = ('recipe__item__name', 'item__name')
    autocomplete_fields = ('recipe', 'item')
    
    fieldsets = (
        ('Recipe Details', {
            'fields': ('recipe', 'item', 'quantity')
        }),
    )
    
    def get_target_item(self, obj):
        return obj.recipe.item.name
    get_target_item.short_description = 'Target Item'
