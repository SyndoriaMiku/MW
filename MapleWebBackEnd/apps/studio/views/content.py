from django.db.models import Count, Prefetch
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.characters.models import RateEvent
from apps.items.models import AuroraEvent, ItemTemplate, LumenEvent
from apps.quests.models import QuestTemplate
from apps.shops.models import ShopCategory, ShopItem, SpecialShop, SpecialShopItem

from ..access import StaffRequiredMixin
from ..forms.content import (
    AuroraEventForm, LumenEventForm, QuestForm, QuestObjectiveFormSet, QuestRewardFormSet, RateEventForm,
    ShopCategoryForm, ShopItemFormSet, SpecialShopForm, SpecialShopItemFormSet,
)
from .base import EditorView, StudioDeleteView, StudioListView


def item_options():
    return [{'id': pk, 'name': name} for pk, name in ItemTemplate.objects.order_by('name').values_list('pk', 'name')]


# ---------- Shops ----------

class ShopListView(StaffRequiredMixin, View):
    """Both kinds of shop on one page."""

    def get(self, request):
        categories = ShopCategory.objects.prefetch_related(
            Prefetch('shop_items', queryset=ShopItem.objects.select_related('item_template')),
        ).order_by('order', 'id')
        special = SpecialShop.objects.prefetch_related(
            Prefetch('items', queryset=SpecialShopItem.objects.select_related('item')),
        ).order_by('order', 'id')
        now = timezone.now()
        return render(request, 'studio/shops/list.html', {
            'section': 'shops', 'categories': categories,
            'special': [{'shop': shop, 'open': shop.is_open(now)} for shop in special],
        })


class ShopCategoryEditorView(EditorView):
    model = ShopCategory
    form_class = ShopCategoryForm
    formset_classes = {'items': ShopItemFormSet}
    template_name = 'studio/shops/category_form.html'
    section = 'shops'
    edit_url_name = 'studio:shop-edit'
    new_url_name = 'studio:shop-new'
    delete_url_name = 'studio:shop-delete'
    list_url_name = 'studio:shop-list'


class ShopCategoryDeleteView(StudioDeleteView):
    model = ShopCategory
    list_url_name = 'studio:shop-list'
    section = 'shops'


class SpecialShopEditorView(EditorView):
    model = SpecialShop
    form_class = SpecialShopForm
    formset_classes = {'items': SpecialShopItemFormSet}
    template_name = 'studio/shops/special_form.html'
    section = 'shops'
    edit_url_name = 'studio:special-shop-edit'
    new_url_name = 'studio:special-shop-new'
    delete_url_name = 'studio:special-shop-delete'
    list_url_name = 'studio:shop-list'

    def after_save(self, obj, form, formsets, extra):
        formset = formsets['items']
        deleted = set(id(f) for f in formset.deleted_forms)
        for item_form in formset.forms:
            if id(item_form) in deleted or not item_form.instance.pk or not item_form.has_changed():
                continue
            item_form.save_recipe()

    def get_extra_context(self, obj, form):
        return {'item_options': item_options()}


class SpecialShopDeleteView(StudioDeleteView):
    model = SpecialShop
    list_url_name = 'studio:shop-list'
    section = 'shops'


# ---------- Quests ----------

class QuestListView(StudioListView):
    model = QuestTemplate
    template_name = 'studio/quests/list.html'
    search_fields = ('name', 'description')
    section = 'quests'

    def get_queryset(self):
        return super().get_queryset().annotate(
            objective_count=Count('objectives', distinct=True), reward_count=Count('rewards', distinct=True),
        ).prefetch_related('prerequisite_quests').order_by('required_level', 'name')


class QuestEditorView(EditorView):
    model = QuestTemplate
    form_class = QuestForm
    formset_classes = {'objectives': QuestObjectiveFormSet, 'rewards': QuestRewardFormSet}
    template_name = 'studio/quests/form.html'
    section = 'quests'
    edit_url_name = 'studio:quest-edit'
    new_url_name = 'studio:quest-new'
    delete_url_name = 'studio:quest-delete'
    list_url_name = 'studio:quest-list'


class QuestDeleteView(StudioDeleteView):
    model = QuestTemplate
    list_url_name = 'studio:quest-list'
    section = 'quests'


# ---------- Events ----------

EVENT_KINDS = {
    'rate': (RateEvent, RateEventForm, 'Event tỉ lệ thưởng', 'EXP, Lumis và tỉ lệ rơi đồ cho mọi người chơi.'),
    'lumen': (LumenEvent, LumenEventForm, 'Event Lumen', 'Tăng tỉ lệ nâng cấp Lumen, giảm vỡ đồ, cộng thêm cấp.'),
    'aurora': (AuroraEvent, AuroraEventForm, 'Event Aurora', 'Tăng tỉ lệ lên bậc Aurora khi reroll.'),
}


def event_running(event, now):
    if not event.is_active:
        return False
    return (event.start_time is None or event.start_time <= now) and (event.end_time is None or event.end_time >= now)


class EventListView(StaffRequiredMixin, View):
    def get(self, request):
        now = timezone.now()
        sections = []
        for kind, (model, _, label, lead) in EVENT_KINDS.items():
            rows = [{'event': event, 'running': event_running(event, now)} for event in model.objects.order_by('-start_time', '-id')]
            sections.append({'kind': kind, 'label': label, 'lead': lead, 'rows': rows})
        return render(request, 'studio/events/list.html', {'section': 'events', 'sections': sections})


class EventEditorView(EditorView):
    template_name = 'studio/events/form.html'
    section = 'events'
    list_url_name = 'studio:event-list'

    def dispatch(self, request, *args, **kwargs):
        kind = kwargs.get('kind')
        if kind not in EVENT_KINDS:
            raise Http404('Unknown event kind.')
        self.kind = kind
        self.model, self.form_class, self.kind_label, self.kind_lead = EVENT_KINDS[kind]
        return super().dispatch(request, *args, **kwargs)

    def edit_url(self, obj):
        return reverse('studio:event-edit', args=[self.kind, obj.pk])

    def new_url(self):
        return reverse('studio:event-new', args=[self.kind])

    def delete_url(self, obj):
        return reverse('studio:event-delete', args=[self.kind, obj.pk])

    def get_extra_context(self, obj, form):
        return {'kind_label': self.kind_label, 'kind_lead': self.kind_lead}


class EventDeleteView(StudioDeleteView):
    list_url_name = 'studio:event-list'
    section = 'events'

    def dispatch(self, request, *args, **kwargs):
        kind = kwargs.pop('kind', None)
        if kind not in EVENT_KINDS:
            raise Http404('Unknown event kind.')
        self.model = EVENT_KINDS[kind][0]
        return super().dispatch(request, *args, **kwargs)
