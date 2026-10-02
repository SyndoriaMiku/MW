from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.items.models import ItemTemplate
from apps.skilles.models import SkillTemplate
from apps.world.models import (
    BossDungeonTemplate, BossStageEnemy, EnemySkill, EnemyTemplate, Location, LootTable,
    NormalDungeonTemplate, NormalStageEnemy, Region,
)

from ..fields import PercentField, StudioModelForm

MAX_ENEMIES_PER_STAGE = 6


class EnemyTemplateForm(StudioModelForm):
    class Meta:
        model = EnemyTemplate
        fields = ('name', 'level', 'is_boss', 'base_hp', 'base_mp', 'base_att', 'exp_reward', 'lumis_reward_min', 'lumis_reward_max')
        labels = {
            'name': 'Tên quái', 'level': 'Cấp', 'is_boss': 'Là boss', 'base_hp': 'HP', 'base_mp': 'MP', 'base_att': 'ATT',
            'exp_reward': 'EXP thưởng', 'lumis_reward_min': 'Lumis thưởng từ', 'lumis_reward_max': 'Lumis thưởng đến',
        }

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get('lumis_reward_min'), cleaned.get('lumis_reward_max')
        if low is not None and high is not None and low > high:
            self.add_error('lumis_reward_max', 'Phải lớn hơn hoặc bằng mức thấp nhất.')
        return cleaned


class EnemySkillForm(StudioModelForm):
    class Meta:
        model = EnemySkill
        fields = ('skill_template', 'priority_index', 'initial_cd')
        labels = {'skill_template': 'Skill', 'priority_index': 'Ưu tiên', 'initial_cd': 'Chờ trước lần đầu (lượt)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['skill_template'].queryset = SkillTemplate.objects.filter(
            availability__in=[SkillTemplate.Availability.ENEMY, SkillTemplate.Availability.BOTH],
        ).order_by('name')


EnemySkillFormSet = inlineformset_factory(
    EnemyTemplate, EnemySkill, fk_name='enemy_template', form=EnemySkillForm, extra=0, can_delete=True,
)


class LootTableForm(StudioModelForm):
    base_drop_rate = PercentField(label='Tỉ lệ rơi %', min_value=0, max_value=100)

    class Meta:
        model = LootTable
        fields = ('item_template', 'base_drop_rate', 'min_quantity', 'max_quantity', 'drop_type', 'is_party_shared')
        labels = {
            'item_template': 'Item', 'min_quantity': 'Số lượng từ', 'max_quantity': 'đến',
            'drop_type': 'Độ hiếm', 'is_party_shared': 'Chia cho party',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item_template'].queryset = ItemTemplate.objects.order_by('name')
        self.fields['drop_type'].choices = [
            ('common', 'Thường (tăng theo tỉ lệ rơi đồ)'),
            ('epic', 'Epic (chỉ buff/event tăng)'),
            ('legendary', 'Legendary (không bao giờ tăng)'),
        ]

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get('min_quantity'), cleaned.get('max_quantity')
        if low is not None and high is not None and low > high:
            self.add_error('max_quantity', 'Phải ≥ số lượng thấp nhất.')
        return cleaned


LootTableFormSet = inlineformset_factory(
    EnemyTemplate, LootTable, fk_name='enemy', form=LootTableForm, extra=0, can_delete=True,
)


class DungeonFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.select_related('region').order_by('region__order', 'order')


COMMON_DUNGEON_LABELS = {
    'name': 'Tên dungeon', 'description': 'Mô tả', 'location': 'Nằm ở', 'required_level': 'Cấp yêu cầu',
    'exp_reward': 'EXP khi hoàn thành', 'lumis_reward': 'Lumis khi hoàn thành',
}


class NormalDungeonForm(DungeonFormMixin, StudioModelForm):
    class Meta:
        model = NormalDungeonTemplate
        fields = ('name', 'location', 'required_level', 'stamina_cost', 'exp_reward', 'lumis_reward', 'description')
        labels = {**COMMON_DUNGEON_LABELS, 'stamina_cost': 'Tốn thể lực'}
        help_texts = {'location': 'Chỉ để hiển thị "dungeon A ở thị trấn B".'}
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class BossDungeonForm(DungeonFormMixin, StudioModelForm):
    class Meta:
        model = BossDungeonTemplate
        fields = ('name', 'location', 'required_level', 'time_type', 'max_party_size', 'exp_reward', 'lumis_reward', 'description')
        labels = {**COMMON_DUNGEON_LABELS, 'time_type': 'Reset lượt đánh', 'max_party_size': 'Party tối đa'}
        help_texts = {'time_type': 'Mỗi nhân vật đánh một lần mỗi ngày/tuần/tháng (00:00 theo TIME_ZONE).'}
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class StageEnemyFormSetBase(BaseInlineFormSet):
    """A stage holds at most six enemies in total, counting every row's count."""

    def clean(self):
        super().clean()
        total = sum(
            form.cleaned_data.get('count') or 0
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        )
        if total > MAX_ENEMIES_PER_STAGE:
            raise forms.ValidationError(f'Tổng số quái là {total}; một trận tối đa {MAX_ENEMIES_PER_STAGE} quái.')


def stage_enemy_formset(parent, model):
    form = forms.modelform_factory(
        model, form=StudioModelForm, fields=('enemy', 'count'), labels={'enemy': 'Quái', 'count': 'Số lượng'},
    )
    return inlineformset_factory(parent, model, form=form, formset=StageEnemyFormSetBase, extra=0, can_delete=True)


NormalStageEnemyFormSet = stage_enemy_formset(NormalDungeonTemplate, NormalStageEnemy)
BossStageEnemyFormSet = stage_enemy_formset(BossDungeonTemplate, BossStageEnemy)


class RegionForm(StudioModelForm):
    class Meta:
        model = Region
        fields = ('name', 'order', 'description')
        labels = {'name': 'Tên khu vực', 'order': 'Thứ tự hiển thị', 'description': 'Mô tả'}
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


LocationFormSet = inlineformset_factory(
    Region, Location,
    form=forms.modelform_factory(
        Location, form=StudioModelForm, fields=('name', 'order', 'description'),
        labels={'name': 'Địa điểm', 'order': 'Thứ tự', 'description': 'Mô tả'},
        widgets={'description': forms.TextInput},
    ),
    extra=0, can_delete=True,
)
