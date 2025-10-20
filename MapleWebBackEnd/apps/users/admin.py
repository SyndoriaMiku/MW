from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import GameUser

@admin.register(GameUser)
class GameUserAdmin(UserAdmin):
    """
    Giao diện quản lý tùy chỉnh cho GameUser.
    Kế thừa từ UserAdmin để có các tính năng quản lý mật khẩu và quyền hạn.
    """
    # Các cột hiển thị trên trang danh sách
    list_display = ('username', 'email', 'lumis', 'nova', 'is_staff', 'is_active')
    
    # Bộ lọc ở cạnh phải
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    
    # Thanh tìm kiếm
    search_fields = ('username', 'email')
    
    # Sắp xếp mặc định
    ordering = ('username',)
    
    # Biến trường ForeignKey thành ô tìm kiếm thông minh
    autocomplete_fields = ['character']

    # Tùy chỉnh các trường hiển thị trong trang chi tiết.
    # Chúng ta định nghĩa lại 'fieldsets' để khớp với model GameUser.
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email',)}),
        ('Game Data', {'fields': ('lumis', 'nova', 'character')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_admin', 'is_superuser'),
        }),
    )

    # Tùy chỉnh các trường trong trang tạo user mới
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password'),
        }),
    )
    filter_horizontal = ()