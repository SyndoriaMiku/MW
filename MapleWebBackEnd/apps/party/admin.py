from django.contrib import admin
from .models import Party, PartyMember, PartyInvitation
from django.utils import timezone

# ===================================================================
# INLINE ADMINS
# ===================================================================

class PartyMemberInline(admin.TabularInline):
    model = PartyMember
    extra = 0
    min_num = 1
    max_num = 4
    fields = ('character', 'position', 'joined_at')
    readonly_fields = ('joined_at',)
    autocomplete_fields = ('character',)

class PartyInvitationInline(admin.TabularInline):
    model = PartyInvitation
    extra = 0
    fields = ('sender', 'receiver', 'status', 'created_at', 'expires_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('sender', 'receiver')

# ===================================================================
# MODEL ADMINS
# ===================================================================

@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'leader', 'member_count', 'max_size', 'created_at')
    list_filter = ('created_at', 'max_size')
    search_fields = ('id', 'name', 'leader__name')
    readonly_fields = ('id', 'created_at')
    autocomplete_fields = ('leader',)
    filter_horizontal = ('members',)
    inlines = [PartyMemberInline, PartyInvitationInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'leader')
        }),
        ('Party Settings', {
            'fields': ('max_size', 'members')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'
    
    actions = ['disband_parties']
    
    def disband_parties(self, request, queryset):
        """Disband selected parties"""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Successfully disbanded {count} parties.')
    disband_parties.short_description = 'Disband selected parties'

@admin.register(PartyMember)
class PartyMemberAdmin(admin.ModelAdmin):
    list_display = ('character', 'party', 'position', 'joined_at')
    list_filter = ('joined_at', 'position')
    search_fields = ('character__name', 'party__name')
    readonly_fields = ('joined_at',)
    autocomplete_fields = ('party', 'character')
    
    fieldsets = (
        ('Member Information', {
            'fields': ('party', 'character', 'position')
        }),
        ('Timestamps', {
            'fields': ('joined_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(PartyInvitation)
class PartyInvitationAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'party', 'status', 'created_at', 'expires_at', 'is_expired')
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('sender__name', 'receiver__name', 'party__name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('party', 'sender', 'receiver')
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('party', 'sender', 'receiver')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_expired(self, obj):
        return obj.expires_at < timezone.now()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
    
    actions = ['accept_invitations', 'decline_invitations', 'expire_invitations']
    
    def accept_invitations(self, request, queryset):
        """Accept selected pending invitations"""
        updated = queryset.filter(status=PartyInvitation.Status.PENDING).update(status=PartyInvitation.Status.ACCEPTED)
        self.message_user(request, f'Successfully accepted {updated} invitations.')
    accept_invitations.short_description = 'Accept selected invitations'
    
    def decline_invitations(self, request, queryset):
        """Decline selected pending invitations"""
        updated = queryset.filter(status=PartyInvitation.Status.PENDING).update(status=PartyInvitation.Status.DECLINED)
        self.message_user(request, f'Successfully declined {updated} invitations.')
    decline_invitations.short_description = 'Decline selected invitations'
    
    def expire_invitations(self, request, queryset):
        """Expire selected pending invitations"""
        updated = queryset.filter(status=PartyInvitation.Status.PENDING).update(status=PartyInvitation.Status.EXPIRED)
        self.message_user(request, f'Successfully expired {updated} invitations.')
    expire_invitations.short_description = 'Expire selected invitations'
