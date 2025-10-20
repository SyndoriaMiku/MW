from django.contrib import admin
from .models import Character, Equipment, CharacterSkill

# Inline Admin for Character's Skills
class CharacterSkillInline(admin.TabularInline):
    """
    Hiển thị và cho phép chỉnh sửa kỹ năng của nhân vật ngay trên trang Character.
    """
    model = CharacterSkill
    extra = 1  # Hiển thị 1 dòng trống để thêm kỹ năng mới
    autocomplete_fields = ['skill_template'] # Giúp tìm kiếm skill dễ dàng

# Inline Admin for Character's Equipment
class EquipmentInline(admin.StackedInline):
    """
    Hiển thị và quản lý trang bị của nhân vật.
    StackedInline phù hợp hơn vì có nhiều trường.
    """
    model = Equipment
    can_delete = False
    verbose_name_plural = 'Equipped Items'
    
    # Giúp việc chọn nhẫn dễ hơn khi có nhiều
    filter_horizontal = ('rings',)
    
    # Biến các trường ForeignKey thành ô tìm kiếm thông minh
    autocomplete_fields = [
        'pendant', 'earring', 'belt', 'face', 'eye', 'hat', 'top', 
        'bottom', 'shoes', 'cape', 'gloves', 'shoulder', 'weapon'
    ]


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    """
    Tùy chỉnh giao diện quản lý chi tiết cho Character.
    """
    # Gắn các inline đã tạo vào trang admin của Character
    inlines = [EquipmentInline, CharacterSkillInline]

    # Các cột hiển thị trên trang danh sách
    list_display = (
        'name', 
        'owner', 
        'level', 
        'character_class', 
        'job'
    )
    
    # Bộ lọc ở cạnh phải
    list_filter = ('level', 'character_class', 'job')
    
    # Thanh tìm kiếm (tìm theo tên nhân vật hoặc tên người sở hữu)
    search_fields = ('name', 'owner__username')
    
    # Các trường chỉ đọc
    readonly_fields = (
        'id', 
        'display_total_hp', 'display_total_mp', 'display_total_att', 'display_total_damage',
        'display_total_str', 'display_total_agi', 'display_total_int'
    )
    
    # Nhóm các trường lại cho giao diện gọn gàng, dễ hiểu
    fieldsets = (
        ('Core Information', {
            'fields': ('id', 'name', 'owner', 'character_class', 'job')
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

# Đăng ký các model còn lại với giao diện admin mặc định (nếu cần truy cập riêng)
# admin.site.register(Equipment)
# admin.site.register(CharacterSkill)