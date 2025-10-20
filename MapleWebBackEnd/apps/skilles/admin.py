from django.contrib import admin
from .models import SpecialEffectTag, EffectTemplate, SkillTemplate

@admin.register(SpecialEffectTag)
class SpecialEffectTagAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý cho các Thẻ hiệu ứng đặc biệt.
    """
    list_display = ('id', 'name')
    search_fields = ('id', 'name')


@admin.register(EffectTemplate)
class EffectTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chi tiết cho các Mẫu hiệu ứng (buff/debuff).
    Bao gồm và cải tiến phần đăng ký đã có.
    """
    # Các trường hiển thị trên trang danh sách
    list_display = ('name', 'duration_turns', 'stacking_rule', 'dispellable')
    
    # Bộ lọc ở cạnh phải
    list_filter = ('stacking_rule', 'dispellable')
    
    # Quan trọng: search_fields để autocomplete ở các app khác hoạt động
    search_fields = ('name', 'description')
    
    # Giao diện thân thiện cho việc chọn special_effects
    filter_horizontal = ('special_effects',)

    # Nhóm các trường lại cho giao diện gọn gàng, khoa học
    fieldsets = (
        ('Core Information', {
            'fields': ('name', 'description', ('duration_turns', 'stacking_rule', 'dispellable'), 'icon')
        }),
        ('Flat Stat Modifiers (Thay đổi dạng số)', {
            'classes': ('collapse',), # Thu gọn mặc định
            'fields': (
                ('flat_hp_change', 'flat_mp_change'),
                ('flat_att_change',),
                ('flat_str_change', 'flat_agi_change', 'flat_int_change'),
            )
        }),
        ('Percentage Stat Modifiers (Thay đổi dạng %)', {
            'classes': ('collapse',),
            'fields': (
                ('percent_hp_change', 'percent_mp_change'),
                ('percent_att_change',),
                ('percent_str_change', 'percent_agi_change', 'percent_int_change'),
            )
        }),
        ('Per-Turn Effects (Hiệu ứng mỗi lượt)', {
            'classes': ('collapse',),
            'fields': ('hp_change_per_turn', 'mp_change_per_turn')
        }),
        ('Rate Modifiers', {
            'classes': ('collapse',),
            'fields': ('drop_rate_change', 'exp_rate_change')
        }),
        ('Special Modifiers', {
            'classes': ('collapse',),
            'fields': (
                ('damage_taken_modifier', 'damage_dealt_modifier'),
                ('health_received_modifier', 'mana_received_modifier'),
                ('health_dealt_modifier', 'mana_dealt_modifier'),
            )
        }),
        ('Other Effects', {
            'fields': ('shields_points', 'cooldown_reduction', 'special_effects')
        }),
    )


@admin.register(SkillTemplate)
class SkillTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chính cho các Mẫu Kỹ năng.
    """
    list_display = ('name', 'job', 'effect_type', 'required_level', 'mp_cost', 'cooldown')
    list_filter = ('job', 'effect_type', 'target_type')
    search_fields = ('name', 'description')
    autocomplete_fields = ['job', 'applies_effect']
    readonly_fields = ('id',)

    fieldsets = (
        ('Core Information', {
            'fields': ('id', 'name', 'description')
        }),
        ('Requirements', {
            'fields': ('job', 'required_level')
        }),
        ('Mechanics', {
            'fields': (
                ('target_type', 'effect_type'),
                ('mp_cost', 'cooldown'),
                ('base_power', 'power_ratio'),
                'applies_effect'
            )
        }),
    )