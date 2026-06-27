from django.contrib import admin
from .models import Character, EquipmentSlotConfig, EquippedItem, CharacterSkill


# ===================================================================
# SECTION: INLINE DEFINITIONS
# ===================================================================

class CharacterSkillInline(admin.TabularInline):
    """
    Hiển thị và cho phép chỉnh sửa kỹ năng của nhân vật ngay trên trang Character.
    """
    model = CharacterSkill
    extra = 1  # Hiển thị 1 dòng trống để thêm kỹ năng mới
    autocomplete_fields = ['skill_template'] # Giúp tìm kiếm skill dễ dàng


class EquippedItemInline(admin.TabularInline):
    """
    Hiển thị và quản lý trang bị của nhân vật thông qua hệ thống slot động.
    """
    model = EquippedItem
    extra = 1
    autocomplete_fields = ['slot', 'item']
    fields = ('slot', 'slot_index', 'item')


# ===================================================================
# SECTION: MAIN MODEL ADMINS
# ===================================================================

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    """
    Tùy chỉnh giao diện quản lý chi tiết cho Character.
    """
    # Gắn các inline đã tạo vào trang admin của Character
    inlines = [EquippedItemInline, CharacterSkillInline]

    # Các cột hiển thị trên trang danh sách
    list_display = (
        'name', 
        'get_owner_username', 
        'level', 
        'character_class', 
        'job'
    )
    
    # Bộ lọc ở cạnh phải
    list_filter = ('level', 'character_class', 'job')
    
    # Thanh tìm kiếm (tìm theo tên nhân vật hoặc tên người sở hữu)
    search_fields = ('name', 'user__username')
    
    # Các trường chỉ đọc
    readonly_fields = (
        'id', 
        'display_total_hp', 'display_total_mp', 'display_total_att', 'display_total_damage',
        'display_total_str', 'display_total_agi', 'display_total_int'
    )
    
    # Nhóm các trường lại cho giao diện gọn gàng, dễ hiểu
    fieldsets = (
        ('Core Information', {
            'fields': ('id', 'name', 'character_class', 'job', 'current_location')
        }),
        ('Leveling & Experience', {
            'fields': ('level', 'current_exp')
        }),
        ('Base Stats (Chỉ số gốc)', {
            'fields': (
                ('base_hp', 'base_mp'), 
                ('base_att',),
                ('base_str', 'base_agi', 'base_int'),
                'drop_rate'
            )
        }),
        ('Calculated Total Stats (Chỉ số tổng - Chỉ xem)', {
            'fields': (
                ('display_total_hp', 'display_total_mp'),
                ('display_total_att', 'display_total_damage'),
                ('display_total_str', 'display_total_agi', 'display_total_int')
            )
        }),
        ('Stamina', {
            'fields': ('max_stamina', 'current_stamina', 'last_stamina_update')
        }),
    )

    # Display owner username via reverse OneToOne relation
    @admin.display(description='Owner', ordering='user__username')
    def get_owner_username(self, obj):
        return obj.user.username if hasattr(obj, 'user') and obj.user else '—'

    # Các phương thức để hiển thị các @cached_property trong admin
    def display_total_hp(self, obj):
        return obj.total_hp
    display_total_hp.short_description = 'Total HP'

    def display_total_mp(self, obj):
        return obj.total_mp
    display_total_mp.short_description = 'Total MP'

    def display_total_att(self, obj):
        return obj.total_att
    display_total_att.short_description = 'Total Attack'
    
    def display_total_damage(self, obj):
        return obj.total_damage
    display_total_damage.short_description = 'Total Damage'

    def display_total_str(self, obj):
        return obj.total_str
    display_total_str.short_description = 'Total STR'

    def display_total_agi(self, obj):
        return obj.total_agi
    display_total_agi.short_description = 'Total AGI'

    def display_total_int(self, obj):
        return obj.total_int
    display_total_int.short_description = 'Total INT'


# ===================================================================
# SECTION: EQUIPMENT SLOT CONFIG
# ===================================================================

@admin.register(EquipmentSlotConfig)
class EquipmentSlotConfigAdmin(admin.ModelAdmin):
    """
    Quản lý cấu hình các slot trang bị.
    Thêm/sửa/xóa slot ở đây — không cần migration.
    """
    list_display = ('slot_type', 'display_name', 'max_count', 'allowed_item_types', 'order')
    search_fields = ('slot_type', 'display_name')
    ordering = ('order',)
    list_editable = ('display_name', 'max_count', 'order')