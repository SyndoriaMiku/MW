from django.contrib import admin
from .models import InventoryItem, AuroraLine

class AuroraLineInline(admin.TabularInline):
    """
    Hiển thị các dòng Aurora của một vật phẩm ngay trên trang chi tiết
    của vật phẩm đó.
    """
    model = AuroraLine
    extra = 1  # Hiển thị 1 dòng trống để thêm dòng Aurora mới
    fields = ('stat_type', 'line_type', 'value')
    verbose_name_plural = 'Aurora Lines'


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    """
    Tùy chỉnh giao diện quản lý cho InventoryItem.
    """
    # Các cột hiển thị trên trang danh sách
    list_display = (
        'template', 
        'owner', 
        'quantity', 
        'lumen_ascend_level', 
        'aurora_level'
    )
    
    # Bộ lọc ở cạnh phải (lọc theo loại vật phẩm)
    list_filter = ('template__item_type',)
    
    # Thanh tìm kiếm (theo tên vật phẩm hoặc tên chủ sở hữu)
    search_fields = ('template__name', 'owner__name')
    
    # Biến các trường ForeignKey thành ô tìm kiếm thông minh
    autocomplete_fields = ('template', 'owner')
    
    # Nhóm các trường lại cho giao diện gọn gàng
    fieldsets = (
        ('Core Information', {
            'fields': ('template', 'owner')
        }),
        ('Item Details & Status', {
            'fields': ('quantity', 'is_untrade', 'expired_at')
        }),
        ('Enhancements', {
            'fields': ('lumen_ascend_level', 'aurora_level')
        }),
    )
    
    # Gắn AuroraLineInline vào trang chi tiết
    inlines = [AuroraLineInline]


@admin.register(AuroraLine)
class AuroraLineAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý riêng cho AuroraLine (hữu ích để xem/tìm kiếm tất cả các dòng).
    """
    list_display = ('inventory_item', 'stat_type', 'line_type', 'value')
    list_filter = ('stat_type', 'line_type')
    search_fields = ('inventory_item__template__name',)
    autocomplete_fields = ['inventory_item']