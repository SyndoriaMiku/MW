from django import forms

from apps.classes.models import CharacterClass, Job
from apps.items.models import (
    TYPE_CHOICES, AuroraModifierRule, BattleConsumableRule, FragmentRestoreRule, ItemTemplate,
    LumenModifierRule, LumenTierProperty, TimedBuffRule,
)

from ..fields import PercentField, StudioModelForm
from ..items_logic import GEAR_TYPES, ITEM_GROUPS, STAT_LABELS, USE_KIND_LABELS, USE_KINDS_BY_TYPE

GROUP_LABELS = {
    'weapon': 'Vũ khí', 'armor': 'Giáp', 'accessory': 'Phụ kiện', 'consumable': 'Tiêu hao', 'etc': 'Khác',
}
TYPE_LABELS = dict(TYPE_CHOICES)


def grouped_type_choices():
    return [
        (GROUP_LABELS[group], [(item_type, TYPE_LABELS[item_type]) for item_type in types])
        for group, types in ITEM_GROUPS.items()
    ]


class ClassChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.name} · {STAT_LABELS.get(obj.main_stat, obj.main_stat)}'


class JobChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        weapon = obj.get_weapon_type_display() if obj.weapon_type else 'mọi vũ khí'
        return f'{obj.name} ({obj.character_class.name}, {weapon})'


class ItemTemplateForm(StudioModelForm):
    item_type = forms.ChoiceField(label='Loại đồ', choices=grouped_type_choices)
    class_restriction = ClassChoiceField(
        label='Class mặc được', queryset=CharacterClass.objects.order_by('name'), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Không chọn = mọi class. Chọn một class để Studio biết chỉ số chính (STR/AGI/INT).',
    )
    job_restriction = JobChoiceField(
        label='Job mặc được', queryset=Job.objects.select_related('character_class').order_by('character_class__name', 'name'),
        required=False, widget=forms.CheckboxSelectMultiple,
        help_text='Không chọn = mọi job của các class trên.',
    )
    use_kind = forms.ChoiceField(
        label='Công dụng', required=False, widget=forms.RadioSelect,
        choices=[(kind, label) for kind, label in USE_KIND_LABELS.items()],
    )

    class Meta:
        model = ItemTemplate
        fields = (
            'name', 'item_type', 'weapon_type', 'minimum_level', 'class_restriction', 'job_restriction',
            'str_boost', 'agi_boost', 'int_boost', 'all_stats_boost', 'att_boost', 'hp_boost', 'mp_boost',
            'drop_rate_boost', 'lumen_tier', 'aurora_tier', 'is_tradeable', 'is_trade_once', 'is_sellable',
            'sell_price', 'expire_after_minutes', 'expires_at', 'description', 'icon_key', 'visual_key',
        )
        labels = {
            'name': 'Tên', 'weapon_type': 'Loại vũ khí', 'minimum_level': 'Cấp tối thiểu',
            'str_boost': 'STR', 'agi_boost': 'AGI', 'int_boost': 'INT', 'all_stats_boost': 'All Stats',
            'att_boost': 'ATT', 'hp_boost': 'HP', 'mp_boost': 'MP', 'drop_rate_boost': 'Tỉ lệ rơi đồ',
            'lumen_tier': 'Bậc Lumen', 'aurora_tier': 'Bậc Aurora', 'is_tradeable': 'Giao dịch được',
            'is_trade_once': 'Chỉ giao dịch 1 lần', 'is_sellable': 'Bán cho NPC được', 'sell_price': 'Giá bán NPC (Lumis)',
            'expire_after_minutes': 'Hết hạn sau (phút)', 'expires_at': 'Hết hạn lúc (UTC)',
            'description': 'Mô tả', 'icon_key': 'Icon key', 'visual_key': 'Visual key',
        }
        help_texts = {
            'weapon_type': 'Job chỉ cầm được đúng loại vũ khí của mình.',
            'all_stats_boost': 'Cộng vào cả STR, AGI và INT.',
            'drop_rate_boost': 'Điểm %: 5 = +5% tỉ lệ rơi đồ thường.',
            'lumen_tier': 'Để trống = không nâng cấp Lumen được.',
            'aurora_tier': 'Để trống = không có dòng tiềm năng Aurora.',
            'expire_after_minutes': 'Tính từ lúc nhận. Item có hạn không giao dịch được.',
            'expires_at': 'Mốc cố định, ví dụ hết event. Có cả hai thì lấy mốc sớm hơn.',
            'icon_key': 'Tên icon bên frontend, không trùng.',
            'visual_key': 'Tên hình khi mặc, không trùng.',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lumen_tier'].queryset = LumenTierProperty.objects.order_by('tier', 'name')
        if self.instance.pk:
            from ..items_logic import USE_RULE_RELATIONS

            self.initial['use_kind'] = next(
                (kind for kind, relation in USE_RULE_RELATIONS.items() if hasattr(self.instance, relation)), '',
            )

    def clean(self):
        cleaned = super().clean()
        item_type = cleaned.get('item_type')
        if item_type is None:
            return cleaned
        if item_type != 'weapon':
            # The select stays filled in the page after switching away from weapon.
            cleaned['weapon_type'] = None
        if item_type not in GEAR_TYPES:
            # Only gear has stats, restrictions and upgrades; keep them empty.
            for field in ('str_boost', 'agi_boost', 'int_boost', 'all_stats_boost', 'att_boost', 'hp_boost', 'mp_boost', 'drop_rate_boost'):
                cleaned[field] = 0
            cleaned['class_restriction'] = CharacterClass.objects.none()
            cleaned['job_restriction'] = Job.objects.none()
            cleaned['lumen_tier'] = cleaned['aurora_tier'] = None

        use_kind = cleaned.get('use_kind') or ''
        if use_kind and use_kind not in USE_KINDS_BY_TYPE.get(item_type, []):
            self.add_error('use_kind', f'Loại "{TYPE_LABELS[item_type]}" không có công dụng này.')

        classes = list(cleaned.get('class_restriction') or [])
        for job in cleaned.get('job_restriction') or []:
            # The game checks class and job separately, so a job outside the
            # chosen classes could never wear it.
            if classes and job.character_class not in classes:
                self.add_error('job_restriction', f'{job.name} thuộc {job.character_class.name}, không nằm trong các class đã chọn.')
            if item_type == 'weapon' and job.weapon_type and cleaned.get('weapon_type') and job.weapon_type != cleaned['weapon_type']:
                self.add_error('job_restriction', f'{job.name} chỉ cầm {job.get_weapon_type_display()}.')
        return cleaned


class BattleConsumableRuleForm(StudioModelForm):
    hp_restore_percent = PercentField(label='Hồi HP theo %', min_value=0, max_value=100, initial=0, required=False)
    mp_restore_percent = PercentField(label='Hồi MP theo %', min_value=0, max_value=100, initial=0, required=False)

    class Meta:
        model = BattleConsumableRule
        fields = ('hp_restore', 'hp_restore_percent', 'mp_restore', 'mp_restore_percent', 'applies_effect', 'target_type', 'cooldown_turns')
        labels = {
            'hp_restore': 'Hồi HP (số)', 'mp_restore': 'Hồi MP (số)', 'applies_effect': 'Gắn hiệu ứng',
            'target_type': 'Dùng cho', 'cooldown_turns': 'Hồi chiêu (lượt)',
        }
        help_texts = {'applies_effect': 'Ví dụ bình tăng ATT: chọn một hiệu ứng buff.'}

    def clean_hp_restore_percent(self):
        return self.cleaned_data['hp_restore_percent'] or 0

    def clean_mp_restore_percent(self):
        return self.cleaned_data['mp_restore_percent'] or 0


class TimedBuffRuleForm(StudioModelForm):
    class Meta:
        model = TimedBuffRule
        fields = (
            'exp_rate_bonus', 'lumis_rate_bonus', 'drop_rate_bonus', 'epic_drop_rate_bonus', 'final_damage_bonus',
            'duration_minutes', 'max_duration_minutes',
        )
        labels = {
            'exp_rate_bonus': 'EXP +%', 'lumis_rate_bonus': 'Lumis +%', 'drop_rate_bonus': 'Rơi đồ thường +%',
            'epic_drop_rate_bonus': 'Rơi đồ Epic +%', 'final_damage_bonus': 'Final damage +%',
            'duration_minutes': 'Thời gian mỗi lần dùng (phút)', 'max_duration_minutes': 'Cộng dồn tối đa (phút)',
        }
        help_texts = {
            'exp_rate_bonus': '100 = x2.', 'final_damage_bonus': 'Không ảnh hưởng hồi máu.',
            'max_duration_minutes': 'Trống = không giới hạn.',
        }


class AuroraModifierRuleForm(StudioModelForm):
    tier_up_chance = PercentField(label='Tỉ lệ lên bậc Aurora %', min_value=0, max_value=100, initial=0, required=False)

    class Meta:
        model = AuroraModifierRule
        fields = (
            'modifier_type', 'max_aurora_target', 'tier_up_chance', 'forced_aurora_level',
            'fixed_stat_type', 'fixed_line_type', 'fixed_value',
        )
        labels = {
            'modifier_type': 'Kiểu đá', 'max_aurora_target': 'Dùng cho đồ Aurora tối đa cấp',
            'forced_aurora_level': 'Đặt cấp Aurora (Force Set)', 'fixed_stat_type': 'Dòng cố định: chỉ số',
            'fixed_line_type': 'Dòng cố định: kiểu', 'fixed_value': 'Dòng cố định: giá trị',
        }
        help_texts = {'tier_up_chance': 'Chỉ đá reroll toàn bộ mới lên bậc được.'}

    def clean_tier_up_chance(self):
        return self.cleaned_data['tier_up_chance'] or 0


class LumenModifierRuleForm(StudioModelForm):
    item_types = forms.MultipleChoiceField(
        label='Áp dụng cho loại đồ', required=False, widget=forms.CheckboxSelectMultiple,
        choices=[(item_type, TYPE_LABELS[item_type]) for item_type in GEAR_TYPES],
        help_text='Không chọn = mọi loại đồ.',
    )

    class Meta:
        model = LumenModifierRule
        fields = ('target_level', 'lumen_tiers', 'item_types')
        labels = {'target_level': 'Đặt cấp Lumen thành', 'lumen_tiers': 'Áp dụng cho bậc Lumen'}
        help_texts = {'lumen_tiers': 'Không chọn = mọi bậc.'}
        widgets = {'lumen_tiers': forms.CheckboxSelectMultiple}


class FragmentRestoreRuleForm(StudioModelForm):
    class Meta:
        model = FragmentRestoreRule
        fields = ('restorable_items',)
        labels = {'restorable_items': 'Khôi phục được'}
        help_texts = {'restorable_items': 'Không chọn = mọi món đồ. Giữ Ctrl để chọn nhiều.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['restorable_items'].queryset = ItemTemplate.objects.filter(item_type__in=GEAR_TYPES).order_by('name')


RULE_FORMS = {
    'battle': BattleConsumableRuleForm,
    'timed_buff': TimedBuffRuleForm,
    'aurora_modifier': AuroraModifierRuleForm,
    'lumen_modifier': LumenModifierRuleForm,
    'fragment_restore': FragmentRestoreRuleForm,
}


class CloneItemForm(forms.Form):
    """Copies of a gear item for other classes (or jobs, for weapons)."""
    classes = forms.ModelMultipleChoiceField(
        label='Class', queryset=CharacterClass.objects.order_by('name'), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    jobs = forms.ModelMultipleChoiceField(
        label='Job', queryset=Job.objects.select_related('character_class').order_by('character_class__name', 'name'),
        required=False, widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, item, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item
        self.fields['classes'].label_from_instance = lambda obj: f'{obj.name} · {STAT_LABELS.get(obj.main_stat, obj.main_stat)}'
        self.fields['jobs'].label_from_instance = lambda obj: (
            f'{obj.name} ({obj.character_class.name}, '
            f'{obj.get_weapon_type_display() if obj.weapon_type else "chưa chọn vũ khí"})'
        )

    def clean(self):
        cleaned = super().clean()
        if self.item.item_type == 'weapon':
            if not cleaned.get('jobs'):
                raise forms.ValidationError('Chọn ít nhất một job: vũ khí đi theo loại vũ khí của job.')
            unset = [job.name for job in cleaned['jobs'] if not job.weapon_type]
            if unset:
                raise forms.ValidationError(f'Job chưa chọn loại vũ khí: {", ".join(unset)}.')
        elif not cleaned.get('classes'):
            raise forms.ValidationError('Chọn ít nhất một class.')
        return cleaned
