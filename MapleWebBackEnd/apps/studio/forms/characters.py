from django import forms
from django.forms import inlineformset_factory

from apps.classes.models import CharacterClass, Job
from apps.skilles.models import EffectTemplate, SkillLevelConfig, SkillTemplate, SpecialEffectTag

from ..fields import PercentField, StudioModelForm


class CharacterClassForm(StudioModelForm):
    class Meta:
        model = CharacterClass
        fields = ('name', 'main_stat', 'hp_growth', 'mp_growth', 'str_growth', 'agi_growth', 'int_growth')
        labels = {
            'name': 'Tên class', 'main_stat': 'Chỉ số chính', 'hp_growth': 'HP mỗi cấp', 'mp_growth': 'MP mỗi cấp',
            'str_growth': 'STR mỗi cấp', 'agi_growth': 'AGI mỗi cấp', 'int_growth': 'INT mỗi cấp',
        }
        help_texts = {
            'main_stat': 'Chỉ số quyết định sát thương. Đồ của class này cộng vào chỉ số này.',
        }


class JobForm(StudioModelForm):
    class Meta:
        model = Job
        fields = ('name', 'weapon_type', 'main_stat_weight')
        labels = {'name': 'Tên job', 'weapon_type': 'Loại vũ khí', 'main_stat_weight': 'Hệ số chỉ số chính'}


JobFormSet = inlineformset_factory(CharacterClass, Job, form=JobForm, extra=0, can_delete=True)


class SkillTemplateForm(StudioModelForm):
    power_ratio = PercentField(
        label='Theo sát thương nhân vật', min_value=0, initial=0, required=False,
        help_text='100 = bằng sát thương gốc của nhân vật.',
    )

    class Meta:
        model = SkillTemplate
        fields = (
            'name', 'availability', 'job', 'required_level', 'is_basic_attack', 'effect_type', 'target_type',
            'mp_cost', 'cooldown', 'base_power', 'power_ratio', 'applies_effect', 'boosted_skills',
            'description', 'icon_key', 'visual_key',
        )
        labels = {
            'name': 'Tên skill', 'availability': 'Ai dùng được', 'job': 'Thuộc job', 'required_level': 'Cấp mở khóa',
            'is_basic_attack': 'Là đòn đánh thường của job', 'effect_type': 'Tác dụng', 'target_type': 'Mục tiêu',
            'mp_cost': 'Tốn MP', 'cooldown': 'Hồi chiêu (lượt)', 'base_power': 'Sát thương cộng thêm',
            'applies_effect': 'Gắn hiệu ứng', 'boosted_skills': 'Passive tăng final damage cho',
            'description': 'Mô tả', 'icon_key': 'Icon key', 'visual_key': 'Visual key',
        }
        help_texts = {
            'job': 'Trống = skill chung cho mọi job (hoặc skill của quái).',
            'cooldown': 'N = dùng lại sau N lượt (1 = không có tác dụng).',
            'base_power': 'Cộng thêm sau khi nhân tỉ lệ.',
            'boosted_skills': 'Chỉ cho passive. Không chọn = mọi skill gây sát thương.',
            'description': 'Dùng được {power_ratio}, {base_power}, {mp_cost}, {cooldown}.',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'boosted_skills': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['job'].queryset = Job.objects.select_related('character_class').order_by('character_class__name', 'name')
        self.fields['applies_effect'].queryset = EffectTemplate.objects.order_by('name')
        boosted = SkillTemplate.objects.filter(effect_type=SkillTemplate.EffectType.DAMAGE).order_by('name')
        if self.instance.pk:
            boosted = boosted.exclude(pk=self.instance.pk)
        self.fields['boosted_skills'].queryset = boosted

    def clean_power_ratio(self):
        return self.cleaned_data['power_ratio'] or 0


class SkillLevelConfigForm(StudioModelForm):
    damage_multiplier = PercentField(label='Sát thương', min_value=0, initial=100)
    final_damage_bonus = PercentField(label='Final damage (passive)', min_value=0, initial=0, required=False)

    class Meta:
        model = SkillLevelConfig
        fields = ('skill_level', 'required_char_level', 'damage_multiplier', 'final_damage_bonus', 'required_materials')
        labels = {'skill_level': 'Cấp skill', 'required_char_level': 'Cấp nhân vật', 'required_materials': 'Nguyên liệu nâng cấp'}
        widgets = {'required_materials': forms.TextInput(attrs={'data-materials': ''})}

    def clean_final_damage_bonus(self):
        return self.cleaned_data['final_damage_bonus'] or 0

    def clean_required_materials(self):
        return self.cleaned_data['required_materials'] or []


SkillLevelFormSet = inlineformset_factory(
    SkillTemplate, SkillLevelConfig, form=SkillLevelConfigForm, extra=0, can_delete=True,
)

FRACTION_EFFECT_FIELDS = {
    'percent_hp_change': 'HP tối đa %', 'percent_mp_change': 'MP tối đa %', 'percent_att_change': 'ATT %',
    'percent_str_change': 'STR %', 'percent_agi_change': 'AGI %', 'percent_int_change': 'INT %',
    'damage_power_ratio_per_turn': 'Sát thương mỗi lượt %', 'final_damage_modifier': 'Final damage %',
    'damage_dealt_modifier': 'Sát thương gây ra %', 'damage_taken_modifier': 'Sát thương nhận vào %',
    'health_dealt_modifier': 'Hồi máu cho người khác %', 'health_received_modifier': 'Được hồi máu %',
    'mana_dealt_modifier': 'Hồi MP cho người khác %', 'mana_received_modifier': 'Được hồi MP %',
}


class EffectTemplateForm(StudioModelForm):
    special_effects = forms.ModelMultipleChoiceField(
        label='Hiệu ứng đặc biệt', queryset=SpecialEffectTag.objects.order_by('name'), required=False,
        widget=forms.CheckboxSelectMultiple, help_text='Stun: mất lượt. Silence: chỉ đánh thường và dùng item.',
    )

    class Meta:
        model = EffectTemplate
        fields = (
            'name', 'effect_kind', 'duration_turns', 'stacking_rule', 'dispellable', 'dispel_count', 'special_effects',
            'flat_hp_change', 'percent_hp_change', 'flat_mp_change', 'percent_mp_change',
            'flat_att_change', 'percent_att_change', 'flat_str_change', 'percent_str_change',
            'flat_agi_change', 'percent_agi_change', 'flat_int_change', 'percent_int_change',
            'hp_change_per_turn', 'mp_change_per_turn', 'damage_power_ratio_per_turn',
            'final_damage_modifier', 'damage_dealt_modifier', 'damage_taken_modifier',
            'health_dealt_modifier', 'health_received_modifier', 'mana_dealt_modifier', 'mana_received_modifier',
            'exp_rate_change', 'lumis_rate_change', 'drop_rate_change', 'shields_points', 'cooldown_reduction',
            'description', 'icon_key',
        )
        labels = {
            'name': 'Tên hiệu ứng', 'effect_kind': 'Loại', 'duration_turns': 'Kéo dài (lượt)',
            'stacking_rule': 'Khi gắn lại', 'dispellable': 'Có thể bị gỡ', 'dispel_count': 'Gỡ bao nhiêu hiệu ứng',
            'flat_hp_change': 'HP tối đa', 'flat_mp_change': 'MP tối đa', 'flat_att_change': 'ATT',
            'flat_str_change': 'STR', 'flat_agi_change': 'AGI', 'flat_int_change': 'INT',
            'hp_change_per_turn': 'HP mỗi lượt', 'mp_change_per_turn': 'MP mỗi lượt',
            'exp_rate_change': 'EXP thưởng %', 'lumis_rate_change': 'Lumis thưởng %', 'drop_rate_change': 'Rơi đồ %',
            'shields_points': 'Khiên (chặn sát thương)', 'cooldown_reduction': 'Giảm hồi chiêu (lượt)',
            'description': 'Mô tả', 'icon_key': 'Icon key',
        }
        help_texts = {
            'duration_turns': 'Tính theo lượt của mục tiêu. 0 = tức thời (ví dụ chỉ để gỡ hiệu ứng).',
            'effect_kind': 'Gỡ hiệu ứng: gắn lên đồng minh gỡ debuff, lên địch gỡ buff.',
            'dispel_count': 'Khi gắn, gỡ tối đa chừng này hiệu ứng (0 = không gỡ).',
            'hp_change_per_turn': 'Dương = hồi, âm = mất máu.',
            'exp_rate_change': '100 = x2, tính nếu còn trên người khi thắng.',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stored as fractions (0.2); shown and typed in % like everywhere in Studio.
        for name, label in FRACTION_EFFECT_FIELDS.items():
            per_turn = name == 'damage_power_ratio_per_turn'
            self.fields[name] = PercentField(
                label=label, required=False, initial=0, min_value=0 if per_turn else None,
                help_text='25 = mỗi lượt gây 25% sát thương của người gắn.' if per_turn else '',
            )
            self.fields[name].widget.attrs['class'] = 'input'

    def clean(self):
        cleaned = super().clean()
        for name in FRACTION_EFFECT_FIELDS:
            if cleaned.get(name) is None:
                cleaned[name] = 0
        return cleaned
