"""Building blocks shared by the Studio editors."""
from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.db import router, transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from .. import history
from ..access import StaffRequiredMixin
from ..models import StudioChange


class StudioListView(StaffRequiredMixin, ListView):
    """A searchable list; subclasses name the fields `?q=` searches."""
    paginate_by = 50
    search_fields = ()
    section = ''

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q', '').strip()
        if query and self.search_fields:
            from django.db.models import Q

            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f'{field}__icontains': query})
            queryset = queryset.filter(condition)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(section=self.section, query=self.request.GET.get('q', ''), filter_params=params.urlencode())
        return context


class EditorView(StaffRequiredMixin, View):
    """
    Create (no pk) or edit (pk) one object with its form and inline formsets,
    saving everything in one transaction once all of it is valid. Model
    clean() rules apply as usual, so Studio enforces what the admin does.
    """
    model = None
    form_class = None
    formset_classes = {}  # prefix -> inline formset class
    template_name = None
    section = ''
    edit_url_name = None
    new_url_name = None
    delete_url_name = None
    list_url_name = None

    def get_object(self):
        pk = self.kwargs.get('pk')
        return get_object_or_404(self.model, pk=pk) if pk is not None else None

    def edit_url(self, obj):
        return reverse(self.edit_url_name, args=[obj.pk])

    def new_url(self):
        return reverse(self.new_url_name) if self.new_url_name else None

    def delete_url(self, obj):
        return reverse(self.delete_url_name, args=[obj.pk]) if self.delete_url_name else None

    def get_form_kwargs(self):
        return {}

    def build_formsets(self, instance, data=None, files=None):
        return {
            prefix: formset_class(data, files, instance=instance, prefix=prefix)
            for prefix, formset_class in self.formset_classes.items()
        }

    def extra_forms(self, instance, data=None, files=None):
        """Other forms on the page (e.g. an item's use rule), keyed by name."""
        return {}

    def extra_forms_valid(self, form, extra):
        return all(extra_form.is_valid() for extra_form in extra.values())

    def after_save(self, obj, form, formsets, extra):
        """Save what the formsets do not, inside the same transaction."""

    def extra_changes(self, form, extra):
        """History entries for the extra forms, merged into the saved change."""
        return {}

    def record_history(self, obj, created, form, formsets, extra):
        changes = history.form_changes(form)
        rows = {}
        for prefix, formset in formsets.items():
            row_changes = history.formset_changes(formset)
            if row_changes:
                rows[str(formset.model._meta.verbose_name_plural)] = row_changes
        if rows:
            changes['_rows'] = rows
        changes.update(self.extra_changes(form, extra))
        if not created and not changes:
            return
        action = StudioChange.Action.CREATE if created else StudioChange.Action.UPDATE
        history.record(self.request.user, action, obj, changes=changes)

    def get_extra_context(self, obj, form):
        return {}

    def render_editor(self, obj, form, formsets, extra):
        context = {
            'object': obj,
            'form': form,
            'formsets': formsets,
            'extra': extra,
            'section': self.section,
            'is_new': obj is None or obj.pk is None,
            'list_url': reverse(self.list_url_name),
            'can_add_another': bool(self.new_url()),
            'delete_url': self.delete_url(obj) if obj is not None and obj.pk is not None else None,
            'history_url': history.history_url(obj) if obj is not None and obj.pk is not None else None,
            'opts': self.model._meta,
        }
        context.update(self.get_extra_context(obj, form))
        return render(self.request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        form = self.form_class(instance=obj, **self.get_form_kwargs())
        instance = obj or self.model()
        return self.render_editor(obj, form, self.build_formsets(instance), self.extra_forms(instance))

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        form = self.form_class(request.POST, request.FILES, instance=obj, **self.get_form_kwargs())
        form_valid = form.is_valid()
        # Inline rows validate against the (still unsaved) object being edited.
        formsets = self.build_formsets(form.instance, request.POST, request.FILES)
        extra = self.extra_forms(form.instance, request.POST, request.FILES)
        formsets_valid = all(formset.is_valid() for formset in formsets.values())
        extra_valid = self.extra_forms_valid(form, extra)
        if not (form_valid and formsets_valid and extra_valid):
            messages.error(request, 'Chưa lưu: kiểm tra các ô báo lỗi.')
            return self.render_editor(obj, form, formsets, extra)

        with transaction.atomic():
            saved = form.save()
            for formset in formsets.values():
                formset.instance = saved
                formset.save()
            self.after_save(saved, form, formsets, extra)
            self.record_history(saved, obj is None, form, formsets, extra)
        messages.success(request, f'Đã lưu "{saved}".')
        if '_add_another' in request.POST and self.new_url():
            return redirect(self.new_url())
        return redirect(self.edit_url(saved))


class StudioDeleteView(StaffRequiredMixin, View):
    """Confirm, listing everything the delete would take with it, then delete."""
    model = None
    list_url_name = None
    section = ''
    template_name = 'studio/confirm_delete.html'

    def collect(self, obj):
        collector = NestedObjects(using=router.db_for_write(self.model))
        collector.collect([obj])
        counts = {}
        for model, instances in collector.model_objs.items():
            if model is self.model:
                continue
            counts[model._meta.verbose_name_plural] = len(instances)
        protected = sorted({str(item) for item in collector.protected})
        return counts, protected

    def get(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        counts, protected = self.collect(obj)
        return render(request, self.template_name, {
            'object': obj, 'counts': counts, 'protected': protected, 'section': self.section,
            'opts': self.model._meta, 'cancel_url': reverse(self.list_url_name),
        })

    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        name = str(obj)
        counts, _ = self.collect(obj)
        target = {'target_type': obj._meta.label, 'target_id': obj.pk, 'target_repr': name}
        try:
            with transaction.atomic():
                obj.delete()
                history.record(
                    request.user, StudioChange.Action.DELETE, summary='Xóa kèm: ' + ', '.join(
                        f'{count} {label}' for label, count in counts.items()) if counts else '',
                    **target,
                )
        except ProtectedError:
            messages.error(request, f'Không xóa được "{name}": còn dữ liệu khác đang dùng nó.')
            return redirect(request.path)
        messages.success(request, f'Đã xóa "{name}".')
        return redirect(reverse(self.list_url_name))
