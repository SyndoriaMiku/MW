from django.contrib import admin
from .models import CharacterClass, Job

class JobInline(admin.TabularInline):
    """
    Hiển thị danh sách các Job thuộc về một CharacterClass
    ngay trên trang chi tiết của CharacterClass đó.
    """
    model = Job
    extra = 1  # Hiển thị 1 dòng trống để thêm Job mới
    fields = ('name', 'att_weight', 'main_stat_weight', 'secondary_stat_weight')
    verbose_name_plural = "Associated Jobs"


@admin.register(CharacterClass)
class CharacterClassAdmin(admin.ModelAdmin):
    """
    Tùy chỉnh giao diện quản lý cho CharacterClass.
    """
    # Các cột hiển thị trên trang danh sách
    list_display = ('name', 'main_stat')
    
    # Thanh tìm kiếm
    search_fields = ('name',)
    
    # Nhóm các trường lại cho gọn gàng
    fieldsets = (
        (None, {
            'fields': ('name', 'main_stat')
        }),
        ('Stat Growth Rates (Tốc độ tăng trưởng chỉ số)', {
            'fields': (
                ('hp_growth', 'mp_growth'), 
                ('str_growth', 'agi_growth', 'int_growth')
            )
        }),
    )
    
    # Gắn JobInline vào trang chi tiết
    inlines = [JobInline]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý riêng cho Job (hữu ích để xem/tìm kiếm tất cả các Job).
    """
    # Các cột hiển thị trên trang danh sách
    list_display = ('name', 'character_class', 'att_weight', 'main_stat_weight')
    
    # Bộ lọc ở cạnh phải
    list_filter = ('character_class',)
    
    # Thanh tìm kiếm
    search_fields = ('name',)
    
    # Biến trường ForeignKey thành ô tìm kiếm thông minh
    autocomplete_fields = ['character_class']