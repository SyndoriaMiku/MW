from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.classes.models import CharacterClass
from apps.items.models import AuroraProperty, ItemSet, LumenTierProperty

from .. import history
from ..access import StaffRequiredMixin
from ..forms.tiers import (
    AuroraLineFormSet, AuroraTierForm, ItemSetEffectFormSet, ItemSetForm, LumenAscendFormSet, LumenCostFormSet,
    LumenTierForm,
)
from ..models import StudioChange
from ..tiers_logic import copy_aurora_tier, copy_lumen_tier, tier_class
from .base import EditorView, StudioDeleteView, StudioListView


class LumenTierListView(StudioListView):
    model = LumenTierProperty
    template_name = 'studio/tiers/lumen_list.html'
    search_fields = ('name',)
    section = 'lumen'
    paginate_by = None

    def get_queryset(self):
        return super().get_queryset().annotate(
            cost_count=Count('cost_rules', distinct=True), ascend_count=Count('ascend_rules', distinct=True),
            item_count=Count('itemtemplate', distinct=True),
            cost_min=Min('cost_rules__lumis_cost'), cost_max=Max('cost_rules__lumis_cost'),
        ).order_by('tier', 'name')


class LumenTierEditorView(EditorView):
    model = LumenTierProperty
    form_class = LumenTierForm
    formset_classes = {'costs': LumenCostFormSet, 'ascend': LumenAscendFormSet}
    template_name = 'studio/tiers/lumen_form.html'
    section = 'lumen'
    edit_url_name = 'studio:lumen-edit'
    new_url_name = 'studio:lumen-new'
    delete_url_name = 'studio:lumen-delete'
    list_url_name = 'studio:lumen-list'

    def get_extra_context(self, obj, form):
        return {'copy_url': reverse('studio:lumen-copy', args=[obj.pk]) if obj is not None and obj.pk else None}


class LumenTierDeleteView(StudioDeleteView):
    model = LumenTierProperty
    list_url_name = 'studio:lumen-list'
    section = 'lumen'


class LumenCopyForm(forms.Form):
    classes = forms.ModelMultipleChoiceField(
        label='Tạo bản cho class', queryset=CharacterClass.objects.order_by('name'), required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class LumenTierCopyView(StaffRequiredMixin, View):
    """Copy a Lumen tier as is, or once per chosen class with the main stat moved to theirs."""

    def render_page(self, tier, form):
        return render(self.request, 'studio/tiers/lumen_copy.html', {
            'tier': tier, 'form': form, 'section': 'lumen', 'source_class': tier_class(tier),
        })

    def get(self, request, pk):
        tier = get_object_or_404(LumenTierProperty, pk=pk)
        return self.render_page(tier, LumenCopyForm())

    def post(self, request, pk):
        tier = get_object_or_404(LumenTierProperty, pk=pk)
        form = LumenCopyForm(request.POST)
        if not form.is_valid():
            return self.render_page(tier, form)
        classes = list(form.cleaned_data['classes'])
        if 'plain_copy' not in request.POST and not classes:
            form.add_error('classes', 'Chọn ít nhất một class, hoặc tạo bản sao y hệt.')
            return self.render_page(tier, form)
        with transaction.atomic():
            copies = [copy_lumen_tier(tier)] if 'plain_copy' in request.POST else [
                copy_lumen_tier(tier, character_class=cc) for cc in classes
            ]
            for copy in copies:
                history.record(request.user, StudioChange.Action.CREATE, copy, summary=f'Nhân bản từ "{tier.name}" kèm toàn bộ luật')
        messages.success(request, 'Đã tạo: ' + ', '.join(copy.name for copy in copies))
        return redirect(reverse('studio:lumen-edit', args=[copies[0].pk]) if len(copies) == 1 else reverse('studio:lumen-list'))


class AuroraTierListView(StudioListView):
    model = AuroraProperty
    template_name = 'studio/tiers/aurora_list.html'
    search_fields = ('name',)
    section = 'aurora'
    paginate_by = None

    def get_queryset(self):
        return super().get_queryset().annotate(
            line_count=Count('line_pools', distinct=True), item_count=Count('itemtemplate', distinct=True),
        ).order_by('tier', 'name')


class AuroraTierEditorView(EditorView):
    model = AuroraProperty
    form_class = AuroraTierForm
    formset_classes = {'lines': AuroraLineFormSet}
    template_name = 'studio/tiers/aurora_form.html'
    section = 'aurora'
    edit_url_name = 'studio:aurora-edit'
    new_url_name = 'studio:aurora-new'
    delete_url_name = 'studio:aurora-delete'
    list_url_name = 'studio:aurora-list'

    def get_extra_context(self, obj, form):
        return {'copy_url': reverse('studio:aurora-copy', args=[obj.pk]) if obj is not None and obj.pk else None}


class AuroraTierDeleteView(StudioDeleteView):
    model = AuroraProperty
    list_url_name = 'studio:aurora-list'
    section = 'aurora'


class AuroraTierCopyView(StaffRequiredMixin, View):
    def post(self, request, pk):
        tier = get_object_or_404(AuroraProperty, pk=pk)
        with transaction.atomic():
            copy = copy_aurora_tier(tier)
            history.record(request.user, StudioChange.Action.CREATE, copy, summary=f'Nhân bản từ "{tier.name}" kèm toàn bộ dòng')
        messages.success(request, f'Đã tạo "{copy.name}".')
        return redirect(reverse('studio:aurora-edit', args=[copy.pk]))


class ItemSetListView(StudioListView):
    model = ItemSet
    template_name = 'studio/tiers/set_list.html'
    search_fields = ('name', 'items__name')
    section = 'sets'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('items', 'effects').distinct().order_by('name')


class ItemSetEditorView(EditorView):
    model = ItemSet
    form_class = ItemSetForm
    formset_classes = {'effects': ItemSetEffectFormSet}
    template_name = 'studio/tiers/set_form.html'
    section = 'sets'
    edit_url_name = 'studio:set-edit'
    new_url_name = 'studio:set-new'
    delete_url_name = 'studio:set-delete'
    list_url_name = 'studio:set-list'


class ItemSetDeleteView(StudioDeleteView):
    model = ItemSet
    list_url_name = 'studio:set-list'
    section = 'sets'
