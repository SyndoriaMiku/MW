"""Flat configuration tables edited all at once, one row per record."""
from django.contrib import messages
from django.db import transaction
from django.forms import BaseModelFormSet, modelformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.characters.models import EquipmentSlotConfig
from apps.items.models import AuroraLineCountConfig, AuroraLumisCostRule
from apps.skilles.models import SpecialEffectTag
from apps.world.models import ExperienceTable

from .. import history
from ..access import StaffRequiredMixin
from ..forms.settings import (
    AuroraLineCountForm, AuroraLumisCostForm, EquipmentSlotForm, ExperiencePasteForm, ExperienceRowForm,
    SpecialEffectTagForm, SpecialEffectTagFormSet,
)
from ..models import StudioChange


class TableEditorView(StaffRequiredMixin, View):
    model = None
    form_class = None
    formset_base = BaseModelFormSet
    ordering = ()
    title = ''
    lead = ''
    section = 'settings'
    template_name = 'studio/table.html'

    def formset(self, data=None):
        formset_class = modelformset_factory(self.model, form=self.form_class, formset=self.formset_base, extra=0, can_delete=True)
        return formset_class(data, queryset=self.model.objects.order_by(*self.ordering), prefix='rows')

    def extra_context(self):
        return {}

    def render_page(self, formset, **extra):
        context = {
            'formset': formset, 'title': self.title, 'lead': self.lead, 'section': self.section,
            'history_url': f"{reverse('studio:history')}?type={self.model._meta.label}",
            **self.extra_context(), **extra,
        }
        return render(self.request, self.template_name, context)

    def get(self, request):
        return self.render_page(self.formset())

    def post(self, request):
        formset = self.formset(request.POST)
        if not formset.is_valid():
            messages.error(request, 'Chưa lưu: kiểm tra các ô báo lỗi.')
            return self.render_page(formset)
        with transaction.atomic():
            formset.save()
            changes = history.formset_changes(formset)
            if changes:
                history.record(
                    request.user, StudioChange.Action.UPDATE, target_type=self.model._meta.label,
                    target_id='', target_repr=self.title, changes={'_rows': {self.title: changes}},
                )
        messages.success(request, f'Đã lưu {self.title.lower()}.' if changes else 'Không có thay đổi nào.')
        return redirect(request.path)


class ExperienceTableView(TableEditorView):
    """The EXP table, editable row by row or by pasting a whole table."""
    model = ExperienceTable
    form_class = ExperienceRowForm
    ordering = ('level',)
    title = 'Bảng EXP'
    section = 'experience'
    lead = 'EXP cần để lên từ mỗi cấp sang cấp tiếp theo. Có thể dán cả bảng từ trang thiết kế đường cong.'
    template_name = 'studio/settings/experience.html'

    def extra_context(self):
        rows = list(ExperienceTable.objects.order_by('level').values_list('level', 'required_exp'))
        growth = {}
        for (_, previous), (level, required) in zip(rows, rows[1:]):
            growth[level] = round((required / previous - 1) * 100, 1) if previous else None
        return {'growth': growth, 'total': sum(required for _, required in rows), 'levels': len(rows)}

    def get(self, request):
        return self.render_page(self.formset(), paste_form=ExperiencePasteForm())

    def post(self, request):
        if 'paste' not in request.POST:
            return super().post(request)
        paste_form = ExperiencePasteForm(request.POST)
        if not paste_form.is_valid():
            messages.error(request, 'Chưa lưu: bảng dán chưa đúng dạng.')
            return self.render_page(self.formset(), paste_form=paste_form)
        table = paste_form.cleaned_data['table']
        with transaction.atomic():
            old = dict(ExperienceTable.objects.values_list('level', 'required_exp'))
            for level, required in table.items():
                ExperienceTable.objects.update_or_create(level=level, defaults={'required_exp': required})
            removed = []
            if paste_form.cleaned_data['replace_all']:
                removed = sorted(set(old) - set(table))
                ExperienceTable.objects.filter(level__in=removed).delete()
            changes = {f'Cấp {level}': [old.get(level), required] for level, required in sorted(table.items()) if old.get(level) != required}
            changes.update({f'Cấp {level}': [old[level], None] for level in removed})
            if changes:
                history.record(request.user, StudioChange.Action.UPDATE, target_type='world.ExperienceTable',
                               target_id='', target_repr=self.title, summary=f'Dán bảng {len(table)} cấp', changes=changes)
        messages.success(request, f'Đã cập nhật {len(changes)} cấp.' if changes else 'Bảng dán giống bảng hiện tại.')
        return redirect(request.path)


class EquipmentSlotTableView(TableEditorView):
    model = EquipmentSlotConfig
    form_class = EquipmentSlotForm
    ordering = ('order', 'id')
    title = 'Ô trang bị'
    section = 'slots'
    lead = 'Các ô đồ của nhân vật và loại đồ được mặc vào mỗi ô. Đổi ở đây không cần sửa code.'


class SpecialEffectTagTableView(TableEditorView):
    model = SpecialEffectTag
    form_class = SpecialEffectTagForm
    formset_base = SpecialEffectTagFormSet
    ordering = ('id',)
    title = 'Tag hiệu ứng đặc biệt'
    section = 'tags'
    lead = 'Gắn vào hiệu ứng để combat xử lý riêng. "stun" (mất lượt) và "silence" (chỉ đánh thường, dùng item) do code dùng nên không xóa hay đổi mã được.'


class AuroraLineCountTableView(TableEditorView):
    model = AuroraLineCountConfig
    form_class = AuroraLineCountForm
    ordering = ('min_item_level',)
    title = 'Số dòng Aurora theo cấp item'
    section = 'aurora-lines'
    lead = 'Item có cấp tối thiểu từ mức này trở lên được tối đa chừng ấy dòng Aurora. Dòng có cấp cao nhất mà item đạt sẽ áp dụng.'


class AuroraLumisCostTableView(TableEditorView):
    model = AuroraLumisCostRule
    form_class = AuroraLumisCostForm
    ordering = ('aurora_level', 'min_item_level')
    title = 'Giá reroll Aurora bằng Lumis'
    section = 'aurora-lumis'
    lead = 'Giá theo cấp Aurora hiện tại của món đồ và cấp item. Với mỗi cấp Aurora, dòng có "từ cấp item" cao nhất mà item đạt sẽ áp dụng. Không có dòng nào = không reroll bằng Lumis được.'
