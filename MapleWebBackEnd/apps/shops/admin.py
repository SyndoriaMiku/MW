from django.contrib import admin
from .models import ShopCategory, ShopItem, SpecialShopItem, SpecialShopItemRecipe

# ===================================================================
# SECTION: REGULAR SHOP ADMIN
# ===================================================================

class ShopItemInline(admin.TabularInline):
    """
    Quản lý các vật phẩm trong một danh mục cửa hàng ngay trên trang ShopCategory.
    """
    model = ShopItem
    extra = 1
    autocomplete_fields = ['item_template']
    fields = ('order', 'item_template', 'price', 'stock', 'required_level')
    verbose_name_plural = "Items in this Category (Vật phẩm trong danh mục)"
    ordering = ('order',)


@admin.register(ShopCategory)
class ShopCategoryAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chính cho các danh mục cửa hàng.
    """
    list_display = ('name', 'order', 'currency_type', 'required_level', 'display_is_active', 'display_is_event')
    list_filter = ('currency_type',)
    search_fields = ('name',)
    
    fieldsets = (
        ('Category Details', {
            'fields': ('name', 'order', 'currency_type')
        }),
        ('Availability & Requirements', {
            'description': "Để trống ngày bắt đầu/kết thúc nếu danh mục luôn có sẵn.",
            'fields': ('required_level', 'start_date', 'end_date')
        }),
    )
    
    inlines = [ShopItemInline]
    
    @admin.display(boolean=True, description='Active?')
    def display_is_active(self, obj):
        return obj.is_active

    @admin.display(boolean=True, description='Event?')
    def display_is_event(self, obj):
        return obj.is_event

# ===================================================================
# SECTION: SPECIAL EXCHANGE SHOP ADMIN
# ===================================================================

class SpecialShopItemRecipeInline(admin.TabularInline):
    """
    Quản lý công thức (các vật phẩm cần thiết) cho một SpecialShopItem.
    """
    model = SpecialShopItemRecipe
    extra = 1
    autocomplete_fields = ['item']
    verbose_name_plural = "Recipe Requirements (Nguyên liệu yêu cầu)"
    fields = ('item', 'quantity')


@admin.register(SpecialShopItem)
class SpecialShopItemAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý các vật phẩm đặc biệt có thể đổi/chế tạo.
    """
    list_display = ('item', 'get_recipe_summary', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('item__name',)
    autocomplete_fields = ['item']
    
    # 'exchange' được quản lý qua inline, nên ẩn nó đi để tránh nhầm lẫn
    exclude = ('exchange',)
    
    inlines = [SpecialShopItemRecipeInline]
    
    @admin.display(description='Recipe')
    def get_recipe_summary(self, obj):
        # Lấy tất cả các nguyên liệu từ inline model
        recipes = obj.specialshopitemrecipe_set.all()
        if not recipes:
            return "No recipe defined"
        # Tạo một chuỗi tóm tắt công thức
        return ", ".join([f"{recipe.quantity}x {recipe.item.name}" for recipe in recipes])