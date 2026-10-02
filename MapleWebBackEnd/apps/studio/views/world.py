from django.db.models import Count, Sum
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from apps.world.models import BossDungeonTemplate, EnemyTemplate, NormalDungeonTemplate, Region

from ..access import StaffRequiredMixin
from ..forms.world import (
    BossDungeonForm, BossStageEnemyFormSet, EnemySkillFormSet, EnemyTemplateForm, LocationFormSet,
    LootTableFormSet, NormalDungeonForm, NormalStageEnemyFormSet, RegionForm,
)
from .base import EditorView, StudioDeleteView, StudioListView


class EnemyListView(StudioListView):
    model = EnemyTemplate
    template_name = 'studio/enemies/list.html'
    search_fields = ('name',)
    section = 'enemies'

    def get_queryset(self):
        return super().get_queryset().annotate(
            loot_count=Count('loot_tables', distinct=True), skill_count=Count('enemy_skills', distinct=True),
        ).order_by('level', 'name')


class EnemyEditorView(EditorView):
    model = EnemyTemplate
    form_class = EnemyTemplateForm
    formset_classes = {'skills': EnemySkillFormSet, 'loot': LootTableFormSet}
    template_name = 'studio/enemies/form.html'
    section = 'enemies'
    edit_url_name = 'studio:enemy-edit'
    new_url_name = 'studio:enemy-new'
    delete_url_name = 'studio:enemy-delete'
    list_url_name = 'studio:enemy-list'


class EnemyDeleteView(StudioDeleteView):
    model = EnemyTemplate
    list_url_name = 'studio:enemy-list'
    section = 'enemies'


DUNGEON_KINDS = {
    'normal': (NormalDungeonTemplate, NormalDungeonForm, NormalStageEnemyFormSet, 'Dungeon thường'),
    'boss': (BossDungeonTemplate, BossDungeonForm, BossStageEnemyFormSet, 'Dungeon boss'),
}


class DungeonListView(StaffRequiredMixin, View):
    def get(self, request):
        def rows(model):
            return model.objects.select_related('location__region').annotate(
                enemy_total=Sum('stage_enemies__count'),
            ).order_by('required_level', 'name')

        return render(request, 'studio/dungeons/list.html', {
            'section': 'dungeons', 'normal': rows(NormalDungeonTemplate), 'boss': rows(BossDungeonTemplate),
        })


class DungeonEditorView(EditorView):
    template_name = 'studio/dungeons/form.html'
    section = 'dungeons'
    list_url_name = 'studio:dungeon-list'

    def dispatch(self, request, *args, **kwargs):
        kind = kwargs.get('kind')
        if kind not in DUNGEON_KINDS:
            raise Http404('Unknown dungeon kind.')
        self.kind = kind
        self.model, self.form_class, formset, self.kind_label = DUNGEON_KINDS[kind]
        self.formset_classes = {'enemies': formset}
        return super().dispatch(request, *args, **kwargs)

    # Dungeon URLs carry the kind (normal/boss).
    def edit_url(self, obj):
        return reverse('studio:dungeon-edit', args=[self.kind, obj.pk])

    def new_url(self):
        return reverse('studio:dungeon-new', args=[self.kind])

    def delete_url(self, obj):
        return reverse('studio:dungeon-delete', args=[self.kind, obj.pk])

    def get_extra_context(self, obj, form):
        return {'kind': self.kind, 'kind_label': self.kind_label}


class DungeonDeleteView(StudioDeleteView):
    list_url_name = 'studio:dungeon-list'
    section = 'dungeons'

    def dispatch(self, request, *args, **kwargs):
        kind = kwargs.pop('kind', None)
        if kind not in DUNGEON_KINDS:
            raise Http404('Unknown dungeon kind.')
        self.model = DUNGEON_KINDS[kind][0]
        return super().dispatch(request, *args, **kwargs)


class RegionListView(StudioListView):
    model = Region
    template_name = 'studio/regions/list.html'
    search_fields = ('name', 'locations__name')
    section = 'regions'
    paginate_by = None

    def get_queryset(self):
        return super().get_queryset().prefetch_related('locations').distinct().order_by('order', 'name')


class RegionEditorView(EditorView):
    model = Region
    form_class = RegionForm
    formset_classes = {'locations': LocationFormSet}
    template_name = 'studio/regions/form.html'
    section = 'regions'
    edit_url_name = 'studio:region-edit'
    new_url_name = 'studio:region-new'
    delete_url_name = 'studio:region-delete'
    list_url_name = 'studio:region-list'


class RegionDeleteView(StudioDeleteView):
    model = Region
    list_url_name = 'studio:region-list'
    section = 'regions'
