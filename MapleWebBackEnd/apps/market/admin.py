from django.contrib import admin
from .models import Trade, TradeItem, Listing, Transaction

# ===================================================================
# SECTION: PLAYER-TO-PLAYER TRADING
# ===================================================================

class TradeItemInline(admin.TabularInline):
    """
    Hiển thị các vật phẩm được trao đổi ngay trên trang chi tiết của Trade.
    """
    model = TradeItem
    extra = 1
    autocomplete_fields = ['item']
    verbose_name_plural = "Items in Trade"
    
    # Sắp xếp các trường cho gọn
    fields = ('item', 'is_sender')


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý cho các giao dịch trực tiếp giữa người chơi.
    """
    list_display = ('id', 'sender', 'receiver', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('sender__username', 'receiver__username')
    autocomplete_fields = ('sender', 'receiver')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Trade Details', {
            'fields': ('sender', 'receiver', 'status', 'created_at')
        }),
        ("Sender's Offer", {
            'fields': ('sender_lumis',)
        }),
        ("Receiver's Offer", {
            'fields': ('receiver_lumis',)
        }),
    )
    
    inlines = [TradeItemInline]


# ===================================================================
# SECTION: MARKETPLACE LISTINGS & TRANSACTIONS
# ===================================================================

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý các vật phẩm được đăng bán trên thị trường.
    """
    list_display = ('id', 'item', 'seller', 'price', 'quantity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('seller__username', 'item__template__name')
    autocomplete_fields = ('seller', 'item')
    
    # Tự động cập nhật is_active thành False khi lưu từ admin
    def save_model(self, request, obj, form, change):
        if not obj.is_active:
            # logic to handle deactivation if needed
            pass
        super().save_model(request, obj, form, change)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Giao diện xem lại lịch sử giao dịch trên thị trường.
    """
    list_display = ('id', 'listing_info', 'buyer', 'seller', 'created_at')
    search_fields = ('buyer__username', 'seller__username', 'listing__item__template__name')
    readonly_fields = ('listing', 'buyer', 'seller', 'created_at')
    
    # Không cho phép thêm mới hoặc xóa Transaction từ admin
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
        
    @admin.display(description='Item from Listing')
    def listing_info(self, obj):
        if obj.listing and obj.listing.item:
            return str(obj.listing.item.template)
        return "N/A"