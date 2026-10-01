from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import GameUser, NovaTransaction

@admin.register(GameUser)
class GameUserAdmin(UserAdmin):
    """
    Giao diện quản lý tùy chỉnh cho GameUser.
    Kế thừa từ UserAdmin để có các tính năng quản lý mật khẩu và quyền hạn.
    """
    # Các cột hiển thị trên trang danh sách
    list_display = ('username', 'email', 'lumis', 'nova', 'is_staff', 'is_active', 'last_login')
    
    # Bộ lọc ở cạnh phải
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    
    # Thanh tìm kiếm
    search_fields = ('username', 'email')
    
    # Sắp xếp mặc định
    ordering = ('username',)

    # Nova là tiền premium: chỉ đổi qua sổ giao dịch Nova (Nova Transactions).
    readonly_fields = ('nova', 'last_login')

    # Tùy chỉnh các trường hiển thị trong trang chi tiết.
    # Chúng ta định nghĩa lại 'fieldsets' để khớp với model GameUser.
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email', 'last_login')}),
        ('Game Data', {'fields': ('character', 'lumis', 'nova')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_admin', 'is_superuser'),
        }),
    )

    # Tùy chỉnh các trường trong trang tạo user mới
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    filter_horizontal = ()


class NovaTransactionForm(forms.ModelForm):
    """Admins only record donations and manual adjustments; purchases come from the shop."""
    kind = forms.ChoiceField(choices=[
        (NovaTransaction.Kind.DONATION, NovaTransaction.Kind.DONATION.label),
        (NovaTransaction.Kind.ADJUSTMENT, NovaTransaction.Kind.ADJUSTMENT.label),
    ])

    class Meta:
        model = NovaTransaction
        fields = ('user', 'kind', 'amount', 'reference', 'description', 'note')


@admin.register(NovaTransaction)
class NovaTransactionAdmin(admin.ModelAdmin):
    """
    Sổ giao dịch Nova. Cộng Nova khi nhận donate: thêm một dòng 'Donation'
    với mã donate làm reference (mỗi mã chỉ cộng được một lần). 'description'
    hiện cho người chơi, 'note' chỉ admin xem.
    Các dòng đã ghi không sửa/xóa được; muốn điều chỉnh thì thêm dòng 'Admin adjustment'.
    """
    form = NovaTransactionForm
    list_display = ('created_at', 'user', 'kind', 'amount', 'balance_after', 'reference', 'created_by')
    list_filter = ('kind',)
    search_fields = ('user__username', 'reference', 'description', 'note')
    autocomplete_fields = ('user',)
    date_hierarchy = 'created_at'

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        from .nova_service import record_nova_transaction

        obj.created_by = request.user
        record_nova_transaction(obj)