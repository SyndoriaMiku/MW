from django.db.models import Count, Prefetch, Q

from apps.characters.models import Character
from apps.classes.models import CharacterClass, Job
from apps.items.models import ItemTemplate
from apps.skilles.models import EffectTemplate, SkillTemplate

from ..forms.characters import (
    CharacterClassForm, EffectTemplateForm, FRACTION_EFFECT_FIELDS, JobFormSet, SkillLevelFormSet, SkillTemplateForm,
)
from ..items_logic import STAT_LABELS
from .base import EditorView, StudioDeleteView, StudioListView

GROWTH_PREVIEW_LEVELS = (1, 10, 30, 50, 100, 200)


class ClassListView(StudioListView):
    model = CharacterClass
    template_name = 'studio/classes/list.html'
    search_fields = ('name', 'job__name')
    section = 'classes'
    paginate_by = None

    def get_queryset(self):
        players = [SkillTemplate.Availability.PLAYER, SkillTemplate.Availability.BOTH]
        jobs = Job.objects.annotate(
            skill_count=Count('skills', distinct=True),
            basic_attacks=Count('skills', filter=Q(skills__is_basic_attack=True, skills__availability__in=players), distinct=True),
        ).order_by('name')
        return super().get_queryset().prefetch_related(Prefetch('job_set', queryset=jobs)).order_by('name').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stat_labels'] = STAT_LABELS
        return context


class ClassEditorView(EditorView):
    model = CharacterClass
    form_class = CharacterClassForm
    formset_classes = {'jobs': JobFormSet}
    template_name = 'studio/classes/form.html'
    section = 'classes'
    edit_url_name = 'studio:class-edit'
    new_url_name = 'studio:class-new'
    delete_url_name = 'studio:class-delete'
    list_url_name = 'studio:class-list'

    def get_extra_context(self, obj, form):
        # A new character's stats, the starting point of the growth preview.
        base = [Character._meta.get_field(f'base_{stat}').default for stat in ('hp', 'mp', 'str', 'agi', 'int')]
        return {'preview_levels': GROWTH_PREVIEW_LEVELS, 'base_stats': base}


class ClassDeleteView(StudioDeleteView):
    model = CharacterClass
    list_url_name = 'studio:class-list'
    section = 'classes'


class SkillListView(StudioListView):
    model = SkillTemplate
    template_name = 'studio/skills/list.html'
    search_fields = ('name', 'description')
    section = 'skills'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('job__character_class', 'applies_effect').annotate(
            level_count=Count('level_configs'),
        ).order_by('job__character_class__name', 'job__name', 'required_level', 'name')
        availability = self.request.GET.get('availability')
        if availability in SkillTemplate.Availability.values:
            queryset = queryset.filter(availability=availability)
        job = self.request.GET.get('job')
        if job == 'none':
            queryset = queryset.filter(job__isnull=True)
        elif job and job.isdigit():
            queryset = queryset.filter(job=job)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            jobs=Job.objects.select_related('character_class').order_by('character_class__name', 'name'),
            availabilities=SkillTemplate.Availability.choices,
            job_filter=self.request.GET.get('job', ''), availability=self.request.GET.get('availability', ''),
        )
        return context


class SkillEditorView(EditorView):
    model = SkillTemplate
    form_class = SkillTemplateForm
    formset_classes = {'levels': SkillLevelFormSet}
    template_name = 'studio/skills/form.html'
    section = 'skills'
    edit_url_name = 'studio:skill-edit'
    new_url_name = 'studio:skill-new'
    delete_url_name = 'studio:skill-delete'
    list_url_name = 'studio:skill-list'

    def get_extra_context(self, obj, form):
        return {'item_options': [{'id': pk, 'name': name} for pk, name in ItemTemplate.objects.order_by('name').values_list('pk', 'name')]}


class SkillDeleteView(StudioDeleteView):
    model = SkillTemplate
    list_url_name = 'studio:skill-list'
    section = 'skills'


class EffectListView(StudioListView):
    model = EffectTemplate
    template_name = 'studio/effects/list.html'
    search_fields = ('name', 'description')
    section = 'effects'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('special_effects').annotate(
            skill_count=Count('skilltemplate', distinct=True),
        ).order_by('effect_kind', 'name')


class EffectEditorView(EditorView):
    model = EffectTemplate
    form_class = EffectTemplateForm
    template_name = 'studio/effects/form.html'
    section = 'effects'
    edit_url_name = 'studio:effect-edit'
    new_url_name = 'studio:effect-new'
    delete_url_name = 'studio:effect-delete'
    list_url_name = 'studio:effect-list'

    def get_extra_context(self, obj, form):
        stat_rows = [
            ('HP tối đa', form['flat_hp_change'], form['percent_hp_change']),
            ('MP tối đa', form['flat_mp_change'], form['percent_mp_change']),
            ('ATT', form['flat_att_change'], form['percent_att_change']),
            ('STR', form['flat_str_change'], form['percent_str_change']),
            ('AGI', form['flat_agi_change'], form['percent_agi_change']),
            ('INT', form['flat_int_change'], form['percent_int_change']),
        ]
        return {'stat_rows': stat_rows, 'percent_fields': FRACTION_EFFECT_FIELDS}


class EffectDeleteView(StudioDeleteView):
    model = EffectTemplate
    list_url_name = 'studio:effect-list'
    section = 'effects'
