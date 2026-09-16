from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import InventoryItem, AuroraLine, PendingAuroraRoll

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

    readonly_fields = ('template_base_stats',)

    @admin.display(description='Base Stats (from Item Template)')
    def template_base_stats(self, obj):
        """Show the shared template stats and provide the correct edit target."""
        if not obj or not obj.template_id:
            return 'Select an item template and save first.'

        template = obj.template
        change_url = reverse('admin:items_itemtemplate_change', args=(template.pk,))
        summary = (
            f'HP: {template.hp_boost} | MP: {template.mp_boost} | '
            f'ATT: {template.att_boost} | STR: {template.str_boost} | '
            f'AGI: {template.agi_boost} | INT: {template.int_boost} | '
            f'All Stats: {template.all_stats_boost} | '
            f'Drop Rate: {template.drop_rate_boost}'
        )
        return format_html(
            '{}<br><a href="{}">Edit base stats on Item Template</a>'
            '<br><small>Changes apply to every InventoryItem using this template.</small>',
            summary,
            change_url,
        )
    
    # Nhóm các trường lại cho giao diện gọn gàng
    fieldsets = (
        ('Core Information', {
            'fields': ('template', 'owner')
        }),
        ('Base Stats', {
            'fields': ('template_base_stats',)
        }),
        ('Item Details & Status', {
            'fields': ('quantity', 'is_untrade', 'is_destroyed', 'expired_at')
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

@admin.register(PendingAuroraRoll)
class PendingAuroraRollAdmin(admin.ModelAdmin):
    list_display = ('inventory_item', 'modifier_type', 'created_at')
    search_fields = ('inventory_item__template__name',)
    autocomplete_fields = ['inventory_item']
