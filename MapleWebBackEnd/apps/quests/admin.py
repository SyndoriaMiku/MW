from django.contrib import admin
from .models import QuestTemplate, QuestObjective, QuestReward

# ===================================================================
# SECTION: INLINE DEFINITIONS
# ===================================================================

class QuestObjectiveInline(admin.TabularInline):
    """
    Quản lý các mục tiêu của một nhiệm vụ ngay trên trang QuestTemplate.
    """
    model = QuestObjective
    extra = 1  # Hiển thị 1 dòng trống để thêm mục tiêu mới
    verbose_name_plural = 'Quest Objectives (Mục tiêu nhiệm vụ)'
    
    # Kích hoạt tìm kiếm cho các ForeignKey
    autocomplete_fields = ['enemy_to_defeat', 'item_to_collect', 'dungeon_to_clear']
    
    # Nhóm các trường lại cho gọn gàng
    fieldsets = (
        (None, {
            'fields': (
                ('enemy_to_defeat', 'defeat_count'),
                ('item_to_collect', 'collect_count'),
                ('dungeon_to_clear', 'clear_count'),
            )
        }),
    )


class QuestRewardInline(admin.TabularInline):
    """
    Quản lý các phần thưởng vật phẩm của một nhiệm vụ ngay trên trang QuestTemplate.
    """
    model = QuestReward
    extra = 1
    verbose_name_plural = 'Item Rewards (Phần thưởng vật phẩm)'
    autocomplete_fields = ['item_template']
    fields = ('item_template', 'quantity')


# ===================================================================
# SECTION: MAIN MODEL ADMIN
# ===================================================================

@admin.register(QuestTemplate)
class QuestTemplateAdmin(admin.ModelAdmin):
    """
    Giao diện quản lý chính cho QuestTemplate.
    """
    list_display = ('id', 'name', 'quest_type', 'required_level', 'exp_reward', 'lumis_reward')
    list_filter = ('quest_type',)
    search_fields = ('name', 'description')
    
    # Giao diện thân thiện cho việc chọn các nhiệm vụ tiên quyết
    filter_horizontal = ('prerequisite_quests',)
    
    readonly_fields = ('id',)
    
    # Nhóm các trường lại cho giao diện gọn gàng, khoa học
    fieldsets = (
        ('Core Information', {
            'fields': ('id', 'name', 'description', 'quest_type')
        }),
        ('Requirements', {
            'fields': ('required_level', 'prerequisite_quests')
        }),
        ('Base Rewards', {
            'description': "Phần thưởng vật phẩm được quản lý ở bảng bên dưới.",
            'fields': ('exp_reward', 'lumis_reward')
        }),
    )
    
    # Gắn các inline đã tạo vào trang chi tiết
    inlines = [QuestObjectiveInline, QuestRewardInline]