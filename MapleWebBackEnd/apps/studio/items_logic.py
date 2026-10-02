"""
Item rules Studio adds on top of the models: which stat is a class's main
stat, suggested stats for a new item, a damage estimate using the game's own
formula, and copying an item to another class with its main stat moved.
"""
import re

from apps.characters.models import Character
from apps.items.models import ItemTemplate, LumenTierProperty

# The one-to-one rules that make a 'use'/'etc' item do something, by use kind.
USE_RULE_RELATIONS = {
    'battle': 'battle_consumable_rule',
    'timed_buff': 'timed_buff_rule',
    'aurora_modifier': 'aurora_modifier_rule',
    'lumen_modifier': 'lumen_modifier_rule',
    'fragment_restore': 'fragment_restore_rule',
}
USE_KIND_LABELS = {
    '': 'Không có công dụng',
    'battle': 'Bình dùng trong trận (hồi HP/MP, buff)',
    'timed_buff': 'Buff theo thời gian (x2 EXP, Lumis, drop...)',
    'aurora_modifier': 'Đá Aurora (reroll dòng tiềm năng)',
    'lumen_modifier': 'Đá Lumen (lên thẳng cấp Lumen)',
    'fragment_restore': 'Khôi phục fragment',
}
# Which use kinds each item type may carry (the rule models check the same).
USE_KINDS_BY_TYPE = {
    'use': ['battle', 'timed_buff', 'aurora_modifier', 'lumen_modifier', 'fragment_restore'],
    'etc': ['fragment_restore'],
}

MAIN_STATS = ('str', 'agi', 'int')
STAT_FIELDS = {'str': 'str_boost', 'agi': 'agi_boost', 'int': 'int_boost', 'all': 'all_stats_boost'}
STAT_LABELS = {'str': 'STR', 'agi': 'AGI', 'int': 'INT', 'all': 'All Stats'}

ITEM_GROUPS = {
    'weapon': ('weapon',),
    'armor': ('hat', 'top', 'bottom', 'shoes', 'gloves', 'cape', 'shoulder'),
    'accessory': ('pendant', 'earring', 'ring', 'belt', 'face', 'eye'),
    'consumable': ('use',),
    'etc': ('etc',),
}
GEAR_TYPES = ITEM_GROUPS['weapon'] + ITEM_GROUPS['armor'] + ITEM_GROUPS['accessory']

# Suggested stats per item group, as (constant, per item level). These are a
# starting point to tune, not game rules: Studio only fills them in on request.
STAT_SUGGESTIONS = {
    'weapon': {'att_boost': (10, 1.5), 'main': (2, 0.5)},
    'armor': {'main': (2, 0.4), 'hp_boost': (10, 5)},
    'accessory': {'main': (1, 0.3), 'hp_boost': (5, 2)},
}


def item_group(item_type):
    for group, types in ITEM_GROUPS.items():
        if item_type in types:
            return group
    return 'etc'


def item_main_stat(item):
    """The main stat of the item's class, or of its biggest stat when it has no single class."""
    if item.pk:
        classes = list(item.class_restriction.all())
        if len(classes) == 1:
            return classes[0].main_stat
    values = {stat: getattr(item, STAT_FIELDS[stat]) for stat in (*MAIN_STATS, 'all')}
    best = max(values, key=values.get)
    return best if values[best] > 0 else 'str'


def suggest_stats(item_type, level, main_stat):
    """Starting stats for an item of this type and level, the class's main stat filled in."""
    rules = STAT_SUGGESTIONS.get(item_group(item_type))
    if not rules:
        return {}
    level = max(1, int(level))
    stats = {field: 0 for field in ('hp_boost', 'mp_boost', 'att_boost', *STAT_FIELDS.values())}
    for field, (constant, per_level) in rules.items():
        value = round(constant + per_level * level)
        stats[STAT_FIELDS.get(main_stat, 'str_boost') if field == 'main' else field] = value
    return stats


def character_at_level(job, level):
    """An unsaved character of this job at this level with its class's growth applied."""
    character = Character(job=job, character_class=job.character_class, level=level)
    growth_levels = max(0, level - 1)
    cc = job.character_class
    # Leveling adds int(growth) once per level (Character._level_up).
    character.base_hp += int(cc.hp_growth) * growth_levels
    character.base_mp += int(cc.mp_growth) * growth_levels
    character.base_str += int(cc.str_growth) * growth_levels
    character.base_agi += int(cc.agi_growth) * growth_levels
    character.base_int += int(cc.int_growth) * growth_levels
    return character


def estimate_damage(job, level, boosts):
    """Base damage of this job at this level without and with an item's flat stats."""
    character = character_at_level(job, level)
    all_stats = boosts.get('all_stats_boost', 0)
    base = {
        'str_value': character.base_str, 'agi_value': character.base_agi,
        'int_value': character.base_int, 'att_value': character.base_att,
    }
    with_item = {
        'str_value': base['str_value'] + boosts.get('str_boost', 0) + all_stats,
        'agi_value': base['agi_value'] + boosts.get('agi_boost', 0) + all_stats,
        'int_value': base['int_value'] + boosts.get('int_boost', 0) + all_stats,
        'att_value': base['att_value'] + boosts.get('att_boost', 0),
    }
    return {
        'job': job.name,
        'main_stat': STAT_LABELS[job.character_class.main_stat],
        'level': level,
        'hp': character.base_hp + boosts.get('hp_boost', 0),
        'without_item': character.damage_from(**base),
        'with_item': character.damage_from(**with_item),
        'stats': {key.removesuffix('_value'): value for key, value in with_item.items()},
    }


VARIANT_SUFFIX = re.compile(r'\s*\((AGI|INT|STR) Variant\)$')


def lumen_tier_for_class(tier, source_classes, character_class):
    """
    The matching Lumen tier for another class. Tiers are named per class
    ("Warrior 1-59" -> "Archer 1-59"), or by the admin's "duplicate by class"
    action ("<tier> (AGI Variant)"; STR is the original). Falls back to the
    same tier when no such tier exists.
    """
    if tier is None:
        return tier
    for source in source_classes:
        if source.name in tier.name:
            match = LumenTierProperty.objects.filter(name=tier.name.replace(source.name, character_class.name)).first()
            if match:
                return match
    main_stat = character_class.main_stat
    if main_stat not in MAIN_STATS:
        return tier
    base = VARIANT_SUFFIX.sub('', tier.name)
    name = base if main_stat == 'str' else f'{base} ({main_stat.upper()} Variant)'
    return LumenTierProperty.objects.filter(name=name).first() or tier


COPIED_FIELDS = (
    'description', 'item_type', 'weapon_type', 'minimum_level', 'is_tradeable', 'is_trade_once',
    'is_sellable', 'aurora_tier', 'hp_boost', 'mp_boost', 'att_boost', 'drop_rate_boost',
    'sell_price', 'expire_after_minutes', 'expires_at',
)


def copy_for_class(item, character_class, job=None):
    """
    A copy of a gear item for another class (and job, for weapons): the main
    stat bonus moves to that class's main stat, the restriction and Lumen tier
    follow. Icon/visual keys are unique, so the copy starts without them.
    """
    source_stat = item_main_stat(item)
    target_stat = character_class.main_stat
    copy = ItemTemplate(**{field: getattr(item, field) for field in COPIED_FIELDS})
    for stat, field in STAT_FIELDS.items():
        setattr(copy, field, getattr(item, field))
    if source_stat != target_stat:
        amount = getattr(item, STAT_FIELDS[source_stat])
        setattr(copy, STAT_FIELDS[source_stat], 0)
        setattr(copy, STAT_FIELDS[target_stat], getattr(item, STAT_FIELDS[target_stat]) + amount)
    if job is not None and job.weapon_type:
        copy.weapon_type = job.weapon_type
    source_classes = list(item.class_restriction.all())
    copy.lumen_tier = lumen_tier_for_class(item.lumen_tier, source_classes, character_class)

    name = item.name
    for source in source_classes:
        name = name.replace(source.name, character_class.name)
    if name == item.name:
        name = f'{item.name} ({job.name if job else character_class.name})'
    copy.name = name[:100]
    copy.full_clean()
    copy.save()
    copy.class_restriction.set([character_class])
    copy.job_restriction.set([job] if job is not None else [])
    return copy
