from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.classes.models import CharacterClass, Job
from apps.items.models import ItemTemplate

from .. import history
from ..access import StaffRequiredMixin
from ..models import StudioChange
from ..forms.items import GROUP_LABELS, RULE_FORMS, CloneItemForm, ItemTemplateForm
from ..items_logic import (
    GEAR_TYPES, ITEM_GROUPS, STAT_FIELDS, STAT_LABELS, USE_KIND_LABELS, USE_RULE_RELATIONS,
    copy_for_class, estimate_damage, item_group, item_main_stat, suggest_stats,
)
from .base import EditorView, StudioDeleteView, StudioListView


def use_kind_of(item):
    return next((kind for kind, relation in USE_RULE_RELATIONS.items() if hasattr(item, relation)), '')


class ItemListView(StudioListView):
    model = ItemTemplate
    template_name = 'studio/items/list.html'
    search_fields = ('name', 'description')
    section = 'items'

    def get_queryset(self):
        queryset = super().get_queryset().select_related(*USE_RULE_RELATIONS.values()).prefetch_related(
            Prefetch('class_restriction', queryset=CharacterClass.objects.order_by('name')),
        ).order_by('minimum_level', 'name')
        group = self.request.GET.get('group')
        if group in ITEM_GROUPS:
            queryset = queryset.filter(item_type__in=ITEM_GROUPS[group])
        class_id = self.request.GET.get('class')
        if class_id and class_id.isdigit():
            queryset = queryset.filter(class_restriction=class_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for item in context['object_list']:
            stats = [
                (STAT_LABELS[stat], getattr(item, field), f'stat-{stat}')
                for stat, field in STAT_FIELDS.items() if getattr(item, field)
            ]
            if item.att_boost:
                stats.append(('ATT', item.att_boost, ''))
            if item.hp_boost:
                stats.append(('HP', item.hp_boost, ''))
            kind = use_kind_of(item)
            rows.append({'item': item, 'stats': stats, 'use_kind': USE_KIND_LABELS[kind] if kind else ''})
        context.update(
            rows=rows, groups=GROUP_LABELS, classes=CharacterClass.objects.order_by('name'),
            group=self.request.GET.get('group', ''), class_id=self.request.GET.get('class', ''),
        )
        return context


class ItemEditorView(EditorView):
    model = ItemTemplate
    form_class = ItemTemplateForm
    template_name = 'studio/items/form.html'
    section = 'items'
    edit_url_name = 'studio:item-edit'
    new_url_name = 'studio:item-new'
    delete_url_name = 'studio:item-delete'
    list_url_name = 'studio:item-list'

    def extra_forms(self, instance, data=None, files=None):
        forms = {}
        for kind, form_class in RULE_FORMS.items():
            existing = getattr(instance, USE_RULE_RELATIONS[kind], None) if instance.pk else None
            forms[kind] = form_class(data, files, instance=existing, prefix=f'rule_{kind}')
        return forms

    def selected_kind(self, form):
        if form.is_valid():
            return form.cleaned_data.get('use_kind') or ''
        return self.request.POST.get('use_kind', '')

    def extra_forms_valid(self, form, extra):
        kind = self.selected_kind(form)
        if not kind:
            return True
        rule_form = extra[kind]
        # Rule models check the item they belong to (e.g. 'use' only).
        rule_form.instance.item_template = form.instance
        return rule_form.is_valid()

    def after_save(self, obj, form, formsets, extra):
        kind = form.cleaned_data.get('use_kind') or ''
        for other, relation in USE_RULE_RELATIONS.items():
            if other != kind and hasattr(obj, relation):
                getattr(obj, relation).delete()
        if kind:
            rule_form = extra[kind]
            rule = rule_form.save(commit=False)
            rule.item_template = obj
            rule.save()
            rule_form.save_m2m()

    def extra_changes(self, form, extra):
        kind = form.cleaned_data.get('use_kind') or ''
        if not kind:
            return {}
        return {f'Công dụng: {label}': values for label, values in history.form_changes(extra[kind]).items()}

    def get_extra_context(self, obj, form):
        classes = list(CharacterClass.objects.order_by('name'))
        jobs = list(Job.objects.select_related('character_class').order_by('character_class__name', 'name'))
        return {
            'gear_types': ','.join(GEAR_TYPES),
            'use_types': 'use,etc',
            'builder_data': {
                'classes': [{'id': c.id, 'name': c.name, 'main_stat': c.main_stat} for c in classes],
                'jobs': [
                    {'id': j.id, 'name': j.name, 'class_id': j.character_class_id, 'weapon_type': j.weapon_type or ''}
                    for j in jobs
                ],
                'groups': {item_type: item_group(item_type) for types in ITEM_GROUPS.values() for item_type in types},
                'stat_fields': STAT_FIELDS,
                'stat_labels': STAT_LABELS,
                'suggest_url': reverse('studio:item-suggest'),
                'estimate_url': reverse('studio:item-estimate'),
            },
            'estimate_jobs': jobs,
            'clone_url': reverse('studio:item-clone', args=[obj.pk]) if obj is not None and obj.pk else None,
            'rule_kinds': list(RULE_FORMS),
        }


class ItemDeleteView(StudioDeleteView):
    model = ItemTemplate
    list_url_name = 'studio:item-list'
    section = 'items'


def _int_param(request, name, default=0):
    try:
        return int(float(request.GET.get(name, default)))
    except (TypeError, ValueError):
        return default


class ItemSuggestView(StaffRequiredMixin, View):
    """GET item_type, level, main_stat -> suggested stat fields."""

    def get(self, request):
        main_stat = request.GET.get('main_stat', 'str')
        if main_stat not in STAT_FIELDS:
            main_stat = 'str'
        return JsonResponse({
            'stats': suggest_stats(request.GET.get('item_type', ''), _int_param(request, 'level', 1), main_stat),
        })


class ItemEstimateView(StaffRequiredMixin, View):
    """GET job, level and the item's flat stats -> base damage without/with the item."""

    def get(self, request):
        job = Job.objects.select_related('character_class').filter(pk=_int_param(request, 'job')).first()
        if job is None:
            return JsonResponse({'error': 'Chọn một job để ước tính.'}, status=400)
        level = min(max(_int_param(request, 'level', 1), 1), 300)
        boosts = {field: _int_param(request, field) for field in ('att_boost', 'hp_boost', *STAT_FIELDS.values())}
        return JsonResponse(estimate_damage(job, level, boosts))


class ItemCloneView(StaffRequiredMixin, View):
    """Make copies of a gear item for other classes, its main stat moved to theirs."""

    def get_item(self, pk):
        return get_object_or_404(ItemTemplate.objects.prefetch_related('class_restriction'), pk=pk)

    def render_page(self, item, form):
        return render(self.request, 'studio/items/clone.html', {
            'item': item, 'form': form, 'section': 'items',
            'main_stat': STAT_LABELS[item_main_stat(item)], 'is_gear': item.item_type in GEAR_TYPES,
        })

    def get(self, request, pk):
        item = self.get_item(pk)
        return self.render_page(item, CloneItemForm(item=item))

    def post(self, request, pk):
        item = self.get_item(pk)
        if 'plain_copy' in request.POST:
            return self.plain_copy(item)
        form = CloneItemForm(request.POST, item=item)
        if not form.is_valid():
            return self.render_page(item, form)
        targets = (
            [(job.character_class, job) for job in form.cleaned_data['jobs']] if item.item_type == 'weapon'
            else [(cc, None) for cc in form.cleaned_data['classes']]
        )
        try:
            with transaction.atomic():
                copies = [copy_for_class(item, character_class, job) for character_class, job in targets]
                for copy in copies:
                    history.record(request.user, StudioChange.Action.CREATE, copy, summary=f'Nhân bản cho class khác từ "{item.name}"')
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
            return self.render_page(item, form)
        messages.success(request, 'Đã tạo: ' + ', '.join(copy.name for copy in copies))
        return redirect(reverse('studio:item-list'))

    def plain_copy(self, item):
        classes, jobs = list(item.class_restriction.all()), list(item.job_restriction.all())
        rule_kind = use_kind_of(item)
        rule = getattr(item, USE_RULE_RELATIONS[rule_kind]) if rule_kind else None
        rule_m2m = {}
        if rule is not None:
            rule_m2m = {field.name: list(getattr(rule, field.name).all()) for field in rule._meta.many_to_many}
        source_name = item.name
        with transaction.atomic():
            item.pk = item.id = None
            item.name = f'{item.name} (bản sao)'[:100]
            item.icon_key = item.visual_key = None
            item.save()
            item.class_restriction.set(classes)
            item.job_restriction.set(jobs)
            if rule is not None:
                rule.pk = rule.id = None
                rule.item_template = item
                rule.save()
                for name, values in rule_m2m.items():
                    getattr(rule, name).set(values)
            history.record(self.request.user, StudioChange.Action.CREATE, item, summary=f'Bản sao của "{source_name}"')
        messages.success(self.request, f'Đã tạo bản sao "{item.name}".')
        return redirect(reverse('studio:item-edit', args=[item.pk]))
