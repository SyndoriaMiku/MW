"""
Studio change history: what changed, by whom. Editors call record() inside
the transaction that saves, so a change and its history entry land together.
"""
import datetime
import decimal

from django.db import models
from django.urls import NoReverseMatch, reverse

from .fields import PercentField
from .models import StudioChange

# Player and operations data: only superusers see their history.
PLAYER_DATA_MODELS = {
    'users.GameUser', 'users.NovaTransaction', 'characters.Character', 'inventory.InventoryItem',
    'battles.CombatInstance', 'market.Listing', 'market.Trade', 'market.Transaction', 'party.Party',
}

# Where to open a changed object in Studio, by model label.
EDIT_URLS = {
    'items.ItemTemplate': ('studio:item-edit',),
    'classes.CharacterClass': ('studio:class-edit',),
    'skilles.SkillTemplate': ('studio:skill-edit',),
    'skilles.EffectTemplate': ('studio:effect-edit',),
    'world.EnemyTemplate': ('studio:enemy-edit',),
    'world.NormalDungeonTemplate': ('studio:dungeon-edit', 'normal'),
    'world.BossDungeonTemplate': ('studio:dungeon-edit', 'boss'),
    'world.Region': ('studio:region-edit',),
    'items.LumenTierProperty': ('studio:lumen-edit',),
    'items.AuroraProperty': ('studio:aurora-edit',),
    'items.ItemSet': ('studio:set-edit',),
    'shops.ShopCategory': ('studio:shop-edit',),
    'shops.SpecialShop': ('studio:special-shop-edit',),
    'quests.QuestTemplate': ('studio:quest-edit',),
    'characters.RateEvent': ('studio:event-edit', 'rate'),
    'items.LumenEvent': ('studio:event-edit', 'lumen'),
    'items.AuroraEvent': ('studio:event-edit', 'aurora'),
}
# Configuration tables are edited as a whole, so their changes have no object id.
TABLE_URLS = {
    'world.ExperienceTable': 'studio:experience-table',
    'characters.EquipmentSlotConfig': 'studio:equipment-slots',
    'skilles.SpecialEffectTag': 'studio:effect-tags',
    'items.AuroraLineCountConfig': 'studio:aurora-line-counts',
    'items.AuroraLumisCostRule': 'studio:aurora-lumis-costs',
}


def display(value):
    """A JSON-friendly, readable form of a field value."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat(sep=' ', timespec='minutes') if isinstance(value, datetime.datetime) else value.isoformat()
    if isinstance(value, models.Model):
        return str(value)
    if isinstance(value, dict):
        return {str(key): display(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, models.QuerySet)):
        return [display(item) for item in value]
    return str(value)


def _field_value(field, value):
    if isinstance(field, PercentField):
        return field.prepare_value(value)
    if hasattr(field, 'queryset') and not isinstance(value, (models.Model, models.QuerySet, list, tuple)) and value not in (None, ''):
        # Initial values of choice fields are primary keys; show the object.
        return field.queryset.filter(pk=value).first() or value
    if hasattr(field, 'queryset') and isinstance(value, (list, tuple)):
        pks = [item.pk if isinstance(item, models.Model) else item for item in value]
        return list(field.queryset.filter(pk__in=pks))
    if getattr(field, 'choices', None) and not hasattr(field, 'queryset'):
        # Show choice labels ("Vũ khí") rather than stored codes ("weapon").
        labels = {}
        for key, label in field.choices:
            if isinstance(label, (list, tuple)):
                labels.update({str(k): str(v) for k, v in label})
            else:
                labels[str(key)] = str(label)
        if isinstance(value, (list, tuple)):
            return [labels.get(str(item), item) for item in value]
        return labels.get(str(value), value) if value not in (None, '') else value
    return value


def form_changes(form, fields=None):
    """{label: [old, new]} for every field the form changed."""
    changes = {}
    for name in form.changed_data:
        if fields is not None and name not in fields:
            continue
        field = form.fields[name]
        label = f'{field.label or name}{" (%)" if isinstance(field, PercentField) else ""}'
        old = display(_field_value(field, form.initial.get(name, field.initial)))
        new = display(_field_value(field, form.cleaned_data.get(name)))
        if old != new:
            changes[label] = [old, new]
    return changes


def formset_changes(formset):
    """Added, changed and deleted rows of a saved inline formset."""
    forms_by_pk = {form.instance.pk: form for form in formset.forms if form.instance.pk}
    changed = []
    for obj, field_names in getattr(formset, 'changed_objects', []):
        form = forms_by_pk.get(obj.pk)
        fields = form_changes(form, set(field_names)) if form else {}
        if fields:
            changed.append({'row': str(obj), 'fields': fields})
    result = {
        'added': [str(obj) for obj in getattr(formset, 'new_objects', [])],
        'changed': changed,
        'deleted': [str(obj) for obj in getattr(formset, 'deleted_objects', [])],
    }
    return {key: value for key, value in result.items() if value}


def record(user, action, target=None, *, summary='', changes=None, target_type=None, target_id=None, target_repr=None):
    if target is not None:
        target_type = target_type or target._meta.label
        target_id = target_id if target_id is not None else target.pk
        target_repr = target_repr or str(target)
    return StudioChange.objects.create(
        user=user if getattr(user, 'pk', None) else None,
        username=getattr(user, 'username', '') or '',
        action=action,
        target_type=target_type or '',
        target_id='' if target_id is None else str(target_id),
        target_repr=(target_repr or '')[:255],
        summary=summary[:255],
        changes=changes or {},
    )


def visible_changes(user):
    queryset = StudioChange.objects.all()
    if not user.is_superuser:
        queryset = queryset.exclude(target_type__in=PLAYER_DATA_MODELS)
    return queryset


def target_url(change):
    if change.target_type in TABLE_URLS:
        return reverse(TABLE_URLS[change.target_type])
    route = EDIT_URLS.get(change.target_type)
    if not route or not change.target_id or change.action == StudioChange.Action.DELETE:
        return None
    name, *prefix = route
    try:
        return reverse(name, args=[*prefix, change.target_id])
    except NoReverseMatch:
        return None


def history_url(obj):
    return f"{reverse('studio:history')}?type={obj._meta.label}&id={obj.pk}"
