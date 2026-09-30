from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.inventory.reservations import mutation_block_reason

RATE_KEYS = ('exp_rate', 'lumis_rate', 'drop_rate', 'epic_drop_rate')
# Timed buffs also carry final damage; rate events do not.
BUFF_KEYS = RATE_KEYS + ('final_damage',)


class BuffError(Exception):
    """The item cannot be used as a buff right now; the message says why."""


def rate_bonuses(character, now=None):
    """
    Fractions (1.0 = +100%) added to each gain rate, plus 'final_damage'.
    Buffs from different items do not stack: each rate takes the best running
    buff. Every running RateEvent adds on top of that.
    """
    from .models import CharacterBuff, RateEvent

    now = now or timezone.now()
    bonuses = dict.fromkeys(BUFF_KEYS, 0.0)
    for buff in CharacterBuff.objects.filter(character_id=character.pk, expires_at__gt=now):
        for key in BUFF_KEYS:
            bonuses[key] = max(bonuses[key], getattr(buff, f'{key}_bonus') / 100.0)
    for event in RateEvent.objects.running(now):
        for key in RATE_KEYS:
            bonuses[key] += getattr(event, f'{key}_bonus') / 100.0
    return bonuses


@transaction.atomic
def use_buff_item(character_id, inventory_item_id):
    """
    Use one item that has a TimedBuffRule. A running buff from the same item
    gets the rule's duration added; an expired or missing one starts now.
    A use that would leave more than max_duration_minutes is refused, so the
    item is never spent for nothing.

    Returns (buff, remaining_quantity). Raises InventoryItem.DoesNotExist when
    the character does not own the item, and BuffError when it cannot be used.
    """
    from apps.inventory.models import InventoryItem
    from apps.items.models import TimedBuffRule
    from .models import Character, CharacterBuff

    # Lock the character so two uses of the same buff queue up.
    character = Character.objects.select_for_update().get(pk=character_id)
    item = InventoryItem.objects.select_for_update().select_related('template').get(
        pk=inventory_item_id, owner=character
    )
    try:
        rule = item.template.timed_buff_rule
    except TimedBuffRule.DoesNotExist:
        raise BuffError('This item does not grant a buff.')
    blocked_reason = mutation_block_reason(item)
    if blocked_reason:
        raise BuffError(blocked_reason)

    now = timezone.now()
    buff = CharacterBuff.objects.filter(character=character, source_template=item.template).first()
    if buff is None:
        buff = CharacterBuff(character=character, source_template=item.template)
    duration = timedelta(minutes=rule.duration_minutes)
    if buff.pk and buff.expires_at > now:
        new_expiry = buff.expires_at + duration
    else:
        buff.started_at = now
        new_expiry = now + duration
    if rule.max_duration_minutes is not None and new_expiry - now > timedelta(minutes=rule.max_duration_minutes):
        raise BuffError(f'This buff can have at most {rule.max_duration_minutes} minutes left.')

    buff.expires_at = new_expiry
    for field in TimedBuffRule.BONUS_FIELDS:
        setattr(buff, field, getattr(rule, field))
    buff.save()

    item.quantity -= 1
    if item.quantity <= 0:
        item.delete()
        return buff, 0
    item.save(update_fields=['quantity'])
    return buff, item.quantity
