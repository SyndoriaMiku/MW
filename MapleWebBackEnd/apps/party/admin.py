from django.contrib import admin
from .models import Party, PartyMember, PartyInvitation, PendingPartyLoot

# ===================================================================
# SECTION: INLINE DEFINITIONS
# ===================================================================

class PartyMemberInline(admin.TabularInline):
    """
    Hiển thị và quản lý thành viên trong một Party ngay trên trang chi tiết của Party.
    """
    model = PartyMember
    extra = 1  # Hiển thị 1 dòng trống để thêm thành viên
    autocomplete_fields = ['character']
    fields = ('character', 'position', 'joined_at')
    readonly_fields = ('joined_at',)
    verbose_name_plural = "Party Members (by position)"


class PartyInvitationInline(admin.TabularInline):
    """
    Hiển thị các lời mời đã được gửi cho Party ngay trên trang chi tiết của Party.
    """
    model = PartyInvitation
    extra = 0 # Thường chỉ xem, không tạo mới từ đây
    autocomplete_fields = ['sender', 'receiver']
    fields = ('sender', 'receiver', 'status', 'expires_at')
    readonly_fields = ('expires_at',)
    verbose_name_plural = "Party Invitations"


# ===================================================================
# SECTION: MAIN MODEL ADMINS
# ===================================================================

@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chính cho Party.
    """
    list_display = ('name', 'leader', 'get_member_count', 'max_size', 'created_at')
    search_fields = ('name', 'leader__name')
    autocomplete_fields = ('leader',)
    readonly_fields = ('id', 'created_at')

    fieldsets = (
        ('Party Information', {
            'fields': ('id', 'name', 'leader', 'max_size', 'created_at')
        }),
    )

    inlines = [PartyMemberInline, PartyInvitationInline]

    @admin.display(description='Current Members')
    def get_member_count(self, obj):
        # Đếm số lượng thành viên thông qua model PartyMember
        return obj.party_members.count()


@admin.register(PartyInvitation)
class PartyInvitationAdmin(admin.ModelAdmin):
    """
    Giao diện riêng để quản lý tất cả các lời mời trong game.
    """
    list_display = ('party', 'sender', 'receiver', 'status', 'expires_at')
    list_filter = ('status',)
    search_fields = ('party__name', 'sender__name', 'receiver__name')
    autocomplete_fields = ('party', 'sender', 'receiver')
    readonly_fields = ('created_at', 'expires_at')

# admin.site.register(PartyMember)

@admin.register(PendingPartyLoot)
class PendingPartyLootAdmin(admin.ModelAdmin):
    list_display = ('party', 'item_template', 'quantity', 'dropped_at')
    search_fields = ('party__name', 'item_template__name')
    autocomplete_fields = ('party', 'item_template')
    readonly_fields = ('dropped_at',)