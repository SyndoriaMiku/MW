"""Copying Lumen/Aurora tiers with all their rules, optionally for another class."""
from apps.classes.models import CharacterClass
from apps.items.models import AuroraProperty, LumenTierProperty

from .items_logic import MAIN_STATS

STAT_BOOSTS = {'str': 'str_boost', 'agi': 'agi_boost', 'int': 'int_boost'}


def unique_name(model, name):
    """name, or "name (2)", "name (3)"... so a copy never clashes with a unique name."""
    candidate, number = name[:255], 2
    while model.objects.filter(name=candidate).exists():
        candidate = f'{name[:245]} ({number})'
        number += 1
    return candidate


def tier_class(tier):
    """The class whose name appears in the tier's name, if exactly one does."""
    matches = [cc for cc in CharacterClass.objects.all() if cc.name in tier.name]
    return matches[0] if len(matches) == 1 else None


def copy_lumen_tier(tier, *, character_class=None):
    """
    A copy of a Lumen tier with its cost and stat rules. For another class
    the class name in the tier name is swapped and each stat rule's main
    stat bonus moves to that class's main stat.
    """
    source_class = tier_class(tier)
    name = f'{tier.name} (bản sao)'
    if character_class is not None:
        name = (tier.name.replace(source_class.name, character_class.name) if source_class
                else f'{tier.name} ({character_class.name})')
    copy = LumenTierProperty.objects.create(
        name=unique_name(LumenTierProperty, name), tier=tier.tier, max_lumen_level=tier.max_lumen_level,
    )
    for rule in tier.cost_rules.all():
        rule.pk = None
        rule.lumen_tier = copy
        rule.save()
    target_stat = character_class.main_stat if character_class is not None else None
    for rule in tier.ascend_rules.all():
        if target_stat in MAIN_STATS:
            source_stat = source_class.main_stat if source_class and source_class.main_stat in MAIN_STATS else max(
                MAIN_STATS, key=lambda stat: getattr(rule, STAT_BOOSTS[stat]))
            amount = getattr(rule, STAT_BOOSTS[source_stat])
            if source_stat != target_stat:
                setattr(rule, STAT_BOOSTS[source_stat], 0)
                setattr(rule, STAT_BOOSTS[target_stat], getattr(rule, STAT_BOOSTS[target_stat]) + amount)
        rule.pk = None
        rule.lumen_tier = copy
        rule.save()
    return copy


def copy_aurora_tier(tier):
    copy = AuroraProperty.objects.create(
        name=unique_name(AuroraProperty, f'{tier.name} (bản sao)'), tier=tier.tier, max_aurora_level=tier.max_aurora_level,
    )
    for pool in tier.line_pools.all():
        pool.pk = None
        pool.aurora_property = copy
        pool.save()
    return copy
