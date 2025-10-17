from django.contrib import admin
from .models import CombatInstance, Combatant, ActiveEffect

# Inline Admin for Combatant
class CombatantInline(admin.TabularInline):
    """
    Display Combatants within a CombatInstance in the admin interface.
    """
    model = Combatant
    extra = 0
    readonly_fields = ('entity',)

    fieldsets = (
        (None, {
            'fields': (
                'position',
                ('content_type', 'objects_id'),
                'entity',
                'is_player',
                ('current_hp', 'current_mp'),
            ),
        }),
    )
# Inline Admin for ActiveEffect
class ActiveEffectInline(admin.TabularInline):
    """
    Hiển thị danh sách các hiệu ứng đang hoạt động trong trận chiến
    ngay trong trang chi tiết của CombatInstance.
    """
    model = ActiveEffect
    extra = 0
    
    # Giúp việc chọn target và caster dễ dàng hơn
    autocomplete_fields = ['target', 'caster', 'effect_template'] 
    
    fields = ('target', 'effect_template', 'remaining_turns', 'current_stacks', 'caster')


@admin.register(CombatInstance)
class CombatInstanceAdmin(admin.ModelAdmin):
    """
    Tùy chỉnh giao diện quản lý cho CombatInstance.
    """
    # Các cột hiển thị ở trang danh sách
    list_display = (
        'id', 
        'party', 
        'status', 
        'turn_phase', 
        'turn_count', 
        'updated_at'
    )
    
    # Bộ lọc ở cạnh phải
    list_filter = ('status', 'turn_phase')
    
    # Thanh tìm kiếm
    search_fields = ('id', 'party__name')
    
    # Các trường chỉ đọc trong trang chi tiết
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    # Nhóm các trường lại cho gọn gàng
    fieldsets = (
        ('Overview', {
            'fields': ('id', 'party', 'status')
        }),
        ('Turn Information', {
            'fields': ('turn_phase', 'turn_count', 'current_player_position')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    # Gắn các inline vào trang chi tiết
    inlines = [CombatantInline, ActiveEffectInline]

@admin.register(Combatant)
class CombatantAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý riêng cho Combatant (hữu ích để xem tất cả combatant).
    """
    list_display = ('__str__', 'combat_instance_link', 'is_player', 'current_hp', 'current_mp')
    list_filter = ('is_player', 'content_type')
    search_fields = ('objects_id', 'combat_instance__id')
    autocomplete_fields = ['combat_instance']

    def combat_instance_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        link = reverse("admin:battles_combatinstance_change", args=[obj.combat_instance.id])
        return format_html('<a href="{}">{}</a>', link, obj.combat_instance.id)
    combat_instance_link.short_description = 'Combat Instance'


@admin.register(ActiveEffect)
class ActiveEffectAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý riêng cho ActiveEffect.
    """
    list_display = ('__str__', 'target', 'remaining_turns', 'current_stacks', 'caster')
    list_filter = ('effect_template',)
    search_fields = ('target__objects_id', 'effect_template__name')
    autocomplete_fields = ['combat_instance', 'target', 'caster', 'effect_template']
