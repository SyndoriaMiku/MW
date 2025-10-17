from django.contrib import admin
from .models import EffectTemplate

@admin.register(EffectTemplate)
class EffectTemplateAdmin(admin.ModelAdmin):
    """
    Đăng ký EffectTemplate để autocomplete_fields hoạt động.
    """
    # Các trường hiển thị trên trang danh sách cho dễ nhìn
    list_display = ('name', 'description') 
    
    # Quan trọng: Cung cấp trường tìm kiếm cho autocomplete
    search_fields = ('name', 'description')