"""Forms for the flat configuration tables (one row per record, edited as a table)."""
from django import forms

from apps.characters.models import EquipmentSlotConfig
from apps.items.models import TYPE_CHOICES, AuroraLineCountConfig, AuroraLumisCostRule
from apps.skilles.models import SpecialEffectTag
from apps.world.models import ExperienceTable

from ..fields import StudioModelForm


class ExperienceRowForm(StudioModelForm):
    class Meta:
        model = ExperienceTable
        fields = ('level', 'required_exp')
        labels = {'level': 'Cấp', 'required_exp': 'EXP cần để lên cấp tiếp theo'}


class EquipmentSlotForm(StudioModelForm):
    allowed_item_types = forms.MultipleChoiceField(
        label='Loại đồ mặc vào ô này', choices=TYPE_CHOICES, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = EquipmentSlotConfig
        fields = ('order', 'slot_type', 'display_name', 'max_count', 'allowed_item_types')
        labels = {'order': 'Thứ tự', 'slot_type': 'Mã ô', 'display_name': 'Tên hiển thị', 'max_count': 'Số món tối đa'}


# Combat code looks these ids up (SpecialEffectTag.STUN / SILENCE).
PROTECTED_TAGS = {SpecialEffectTag.STUN, SpecialEffectTag.SILENCE}


class SpecialEffectTagForm(StudioModelForm):
    class Meta:
        model = SpecialEffectTag
        fields = ('id', 'name', 'description')
        labels = {'id': 'Mã', 'name': 'Tên', 'description': 'Mô tả'}
        widgets = {'description': forms.TextInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # The id is the primary key: renaming it would make a new tag.
            self.fields['id'].widget.attrs['readonly'] = True

class SpecialEffectTagFormSet(forms.BaseModelFormSet):
    def clean(self):
        super().clean()
        # An existing row posted with another id would be saved as a new tag.
        existing = set(self.get_queryset().values_list('pk', flat=True))
        for form in self.initial_forms:
            if form.cleaned_data and form.cleaned_data.get('id') not in existing:
                raise forms.ValidationError('Không đổi được mã của tag đã có; thêm dòng mới cho tag mới.')
        # Rows marked for deletion skip their own validation, so check here.
        for form in self.deleted_forms:
            if form.instance.pk in PROTECTED_TAGS:
                raise forms.ValidationError(f'Tag "{form.instance.pk}" được code combat dùng, không xóa được.')


class AuroraLineCountForm(StudioModelForm):
    class Meta:
        model = AuroraLineCountConfig
        fields = ('min_item_level', 'max_lines')
        labels = {'min_item_level': 'Từ cấp item', 'max_lines': 'Số dòng Aurora tối đa'}


class AuroraLumisCostForm(StudioModelForm):
    class Meta:
        model = AuroraLumisCostRule
        fields = ('aurora_level', 'min_item_level', 'lumis_cost')
        labels = {'aurora_level': 'Cấp Aurora hiện tại', 'min_item_level': 'Từ cấp item', 'lumis_cost': 'Giá mỗi lần reroll (Lumis)'}


def parse_experience(text):
    """'1:20, 2:41' (or one 'level:exp' / 'level exp' per line) -> {level: exp}."""
    table = {}
    for chunk in text.replace('\n', ',').split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.replace(':', ' ').replace('\t', ' ').split()
        # EXP may use thousands dots as Studio shows them (15.500); levels may not.
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].replace('.', '').isdigit():
            raise forms.ValidationError(f'Không đọc được "{chunk}": mỗi mục là cấp:EXP, ví dụ 10:15500.')
        level, exp = int(parts[0]), int(parts[1].replace('.', ''))
        if level < 1 or exp < 1:
            raise forms.ValidationError(f'"{chunk}": cấp và EXP phải lớn hơn 0.')
        table[level] = exp
    if not table:
        raise forms.ValidationError('Chưa có dòng nào.')
    return table


class ExperiencePasteForm(forms.Form):
    table = forms.CharField(
        label='Dán bảng EXP', widget=forms.Textarea(attrs={'rows': 4, 'class': 'input', 'placeholder': '1:20, 2:41, 3:190, …'}),
        help_text='Dạng cấp:EXP, cách nhau bằng dấu phẩy hoặc xuống dòng (đúng như nút "Sao chép bảng" của trang thiết kế đường cong).',
    )
    replace_all = forms.BooleanField(label='Xóa các cấp không có trong bảng dán', required=False)

    def clean_table(self):
        return parse_experience(self.cleaned_data['table'])
