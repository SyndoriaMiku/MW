from django import forms
from django.forms import inlineformset_factory

from apps.items.models import (
    LINE_TYPE_CHOICES, STATS_CHOICES, TYPE_CHOICES, AuroraLinePool, AuroraProperty, ItemSet, ItemSetEffect,
    ItemTemplate, LumenAscendRule, LumenCostRule, LumenTierProperty,
)

from ..fields import PercentField, StudioModelForm
from ..items_logic import GEAR_TYPES

TYPE_LABELS = dict(TYPE_CHOICES)
GEAR_CHOICES = [(item_type, TYPE_LABELS[item_type]) for item_type in GEAR_TYPES]


class GearTypesField(forms.MultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def __init__(self, **kwargs):
        kwargs.setdefault('choices', GEAR_CHOICES)
        super().__init__(**kwargs)


class LumenTierForm(StudioModelForm):
    class Meta:
        model = LumenTierProperty
        fields = ('name', 'tier', 'max_lumen_level')
        labels = {'name': 'Tên bậc', 'tier': 'Bậc', 'max_lumen_level': 'Cấp Lumen tối đa'}
        help_texts = {'name': 'Nên có tên class và khoảng cấp, ví dụ "Warrior 1-59", để Studio tự chọn bậc cho item.'}


class LumenCostRuleForm(StudioModelForm):
    success_rate = PercentField(label='Thành công %', min_value=0, max_value=100)
    failure_rate = PercentField(label='Thất bại (giữ nguyên) %', min_value=0, max_value=100)
    heavy_failure_rate = PercentField(label='Thất bại nặng %', min_value=0, max_value=100)

    class Meta:
        model = LumenCostRule
        fields = ('current_level', 'lumis_cost', 'success_rate', 'failure_rate', 'heavy_failure_rate')
        labels = {'current_level': 'Từ cấp Lumen', 'lumis_cost': 'Giá (Lumis)'}

    _rates_invalid = False

    def clean(self):
        cleaned = super().clean()
        rates = [cleaned.get(name) for name in ('success_rate', 'failure_rate', 'heavy_failure_rate')]
        if None not in rates and abs(sum(rates) - 1) > 1e-6:
            self._rates_invalid = True
            raise forms.ValidationError(f'Ba tỉ lệ phải cộng lại bằng 100% (đang là {round(sum(rates) * 100, 2)}%).')
        return cleaned

    def _post_clean(self):
        # The model checks the same sum with an English message; one is enough.
        if not self._rates_invalid:
            super()._post_clean()


class LumenAscendRuleForm(StudioModelForm):
    item_types = GearTypesField(label='Loại đồ')

    class Meta:
        model = LumenAscendRule
        fields = ('lumen_level', 'item_types', 'hp_boost', 'mp_boost', 'att_boost', 'str_boost', 'agi_boost', 'int_boost')
        labels = {
            'lumen_level': 'Cấp Lumen', 'hp_boost': 'HP', 'mp_boost': 'MP', 'att_boost': 'ATT',
            'str_boost': 'STR', 'agi_boost': 'AGI', 'int_boost': 'INT',
        }


LumenCostFormSet = inlineformset_factory(LumenTierProperty, LumenCostRule, form=LumenCostRuleForm, extra=0, can_delete=True)
LumenAscendFormSet = inlineformset_factory(LumenTierProperty, LumenAscendRule, form=LumenAscendRuleForm, extra=0, can_delete=True)


class AuroraTierForm(StudioModelForm):
    class Meta:
        model = AuroraProperty
        fields = ('name', 'tier', 'max_aurora_level')
        labels = {'name': 'Tên bậc', 'tier': 'Bậc', 'max_aurora_level': 'Cấp Aurora tối đa'}


class AuroraLinePoolForm(StudioModelForm):
    item_types = GearTypesField(label='Loại đồ')

    class Meta:
        model = AuroraLinePool
        fields = ('aurora_level', 'item_types', 'stat_type', 'line_type', 'value', 'weight')
        labels = {
            'aurora_level': 'Cấp Aurora', 'stat_type': 'Chỉ số', 'line_type': 'Kiểu', 'value': 'Giá trị',
            'weight': 'Trọng số',
        }
        help_texts = {'weight': 'Dòng có trọng số cao ra thường hơn.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['line_type'].choices = [('flat', 'Số'), ('percent', '%')]
        self.fields['stat_type'].choices = STATS_CHOICES


AuroraLineFormSet = inlineformset_factory(AuroraProperty, AuroraLinePool, form=AuroraLinePoolForm, extra=0, can_delete=True)


class ItemSetForm(StudioModelForm):
    items = forms.ModelMultipleChoiceField(
        label='Các món trong set', queryset=ItemTemplate.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = ItemSet
        fields = ('name', 'description', 'items')
        labels = {'name': 'Tên set', 'description': 'Mô tả'}
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['items'].queryset = ItemTemplate.objects.filter(item_type__in=GEAR_TYPES).order_by('minimum_level', 'name')
        self.fields['items'].label_from_instance = lambda item: f'{item.name} (cấp {item.minimum_level}, {TYPE_LABELS[item.item_type]})'


class ItemSetEffectForm(StudioModelForm):
    class Meta:
        model = ItemSetEffect
        fields = ('required_count', 'hp_boost', 'mp_boost', 'att_boost', 'str_boost', 'agi_boost', 'int_boost', 'all_stats_boost')
        labels = {
            'required_count': 'Khi mặc đủ (món)', 'hp_boost': 'HP', 'mp_boost': 'MP', 'att_boost': 'ATT',
            'str_boost': 'STR', 'agi_boost': 'AGI', 'int_boost': 'INT', 'all_stats_boost': 'All Stats',
        }


ItemSetEffectFormSet = inlineformset_factory(ItemSet, ItemSetEffect, form=ItemSetEffectForm, extra=0, can_delete=True)

LINE_TYPE_LABELS = dict(LINE_TYPE_CHOICES)
