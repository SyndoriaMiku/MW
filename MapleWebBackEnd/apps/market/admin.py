from django.contrib import admin
from .models import Trade, TradeItem, Listing, Transaction


class TradeItemInline(admin.TabularInline):
    """Inline for Trade Items"""
    model = TradeItem
    extra = 0
    fields = ('item', 'is_sender')
    autocomplete_fields = ['item']


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    """Admin interface for Trade model"""
    
    list_display = ('sender', 'receiver', 'sender_lumis', 'receiver_lumis', 
                   'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__username', 'receiver__username')
    
    fieldsets = (
        ('Traders', {
            'fields': (('sender', 'receiver'),)
        }),
        ('Lumis Exchange', {
            'fields': (('sender_lumis', 'receiver_lumis'),)
        }),
        ('Status', {
            'fields': ('status', 'created_at')
        }),
    )
    
    readonly_fields = ('created_at',)
    autocomplete_fields = ['sender', 'receiver']
    inlines = [TradeItemInline]
    
    actions = ['approve_trades', 'cancel_trades']
    
    def approve_trades(self, request, queryset):
        """Approve selected trades"""
        updated = queryset.filter(status='pending').update(status='accepted')
        self.message_user(request, f"{updated} trades approved.")
    approve_trades.short_description = "Approve selected trades"
    
    def cancel_trades(self, request, queryset):
        """Cancel selected trades"""
        updated = queryset.filter(status='pending').update(status='cancelled')
        self.message_user(request, f"{updated} trades cancelled.")
    cancel_trades.short_description = "Cancel selected trades"


@admin.register(TradeItem)
class TradeItemAdmin(admin.ModelAdmin):
    """Admin interface for TradeItem model"""
    
    list_display = ('trade', 'item', 'is_sender')
    list_filter = ('is_sender',)
    search_fields = ('trade__sender__username', 'trade__receiver__username', 'item__template__name')
    
    fieldsets = (
        ('Trade Information', {
            'fields': ('trade', 'item', 'is_sender')
        }),
    )
    
    autocomplete_fields = ['trade', 'item']


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    """Admin interface for Listing model"""
    
    list_display = ('item', 'seller', 'price', 'quantity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('seller__username', 'item__template__name')
    
    fieldsets = (
        ('Listing Information', {
            'fields': ('seller', 'item')
        }),
        ('Pricing', {
            'fields': (('price', 'quantity'),)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    autocomplete_fields = ['seller', 'item']
    
    actions = ['activate_listings', 'deactivate_listings']
    
    def activate_listings(self, request, queryset):
        """Activate selected listings"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} listings activated.")
    activate_listings.short_description = "Activate selected listings"
    
    def deactivate_listings(self, request, queryset):
        """Deactivate selected listings"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} listings deactivated.")
    deactivate_listings.short_description = "Deactivate selected listings"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin interface for Transaction model"""
    
    list_display = ('id', 'listing', 'buyer', 'seller', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('buyer__username', 'seller__username', 'listing__item__template__name')
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('id', 'listing')
        }),
        ('Parties', {
            'fields': (('buyer', 'seller'),)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    readonly_fields = ('id', 'created_at')
    autocomplete_fields = ['listing', 'buyer', 'seller']
