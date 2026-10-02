from django.db.models import Q
from django.views.generic import ListView

from .. import history
from ..access import StaffRequiredMixin
from ..models import StudioChange


class HistoryView(StaffRequiredMixin, ListView):
    """Every change made in Studio, newest first; ?type=&id= narrows it to one object."""
    template_name = 'studio/history.html'
    paginate_by = 50

    def get_queryset(self):
        queryset = history.visible_changes(self.request.user)
        params = self.request.GET
        if params.get('type'):
            queryset = queryset.filter(target_type=params['type'])
        if params.get('id'):
            queryset = queryset.filter(target_id=params['id'])
        if params.get('user'):
            queryset = queryset.filter(username=params['user'])
        if params.get('action') in StudioChange.Action.values:
            queryset = queryset.filter(action=params['action'])
        query = params.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(target_repr__icontains=query) | Q(summary__icontains=query) | Q(username__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visible = history.visible_changes(self.request.user)
        params = self.request.GET.copy()
        params.pop('page', None)
        rows = []
        for change in context['object_list']:
            changes = dict(change.changes)
            table_rows = changes.pop('_rows', {})
            rows.append({'change': change, 'fields': changes, 'rows': table_rows, 'url': history.target_url(change)})
        context.update(
            section='history', rows=rows, filter_params=params.urlencode(), params=self.request.GET,
            users=visible.order_by('username').values_list('username', flat=True).distinct(),
            types=visible.order_by('target_type').values_list('target_type', flat=True).distinct(),
            actions=StudioChange.Action.choices,
            one_object=bool(self.request.GET.get('type') and self.request.GET.get('id')),
        )
        return context
