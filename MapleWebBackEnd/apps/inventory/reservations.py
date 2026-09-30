from django.utils import timezone


def character_in_active_battle(character):
    """Return True when the character is a combatant in an in-progress battle."""
    from django.contrib.contenttypes.models import ContentType
    from apps.battles.models import Combatant

    if character is None:
        return False
    return Combatant.objects.filter(
        content_type=ContentType.objects.get_for_model(character),
        objects_id=str(character.pk),
        has_left=False,
        combat_instance__status='in_progress',
    ).exists()


def mutation_block_reason(item, *, role='Item'):
    """Return why `item` may not be upgraded or consumed right now, or None."""
    from apps.market.models import Listing, TradeItem

    if item.is_destroyed:
        return f"{role} is destroyed."
    if item.expired_at and item.expired_at <= timezone.now():
        return f"{role} is expired."
    if Listing.objects.filter(item=item, is_active=True).exists():
        return f"{role} is currently listed on the market."
    if TradeItem.objects.filter(item=item, trade__status='pending').exists():
        return f"{role} is currently in a pending trade."
    return None


def exclude_expired(queryset, now=None):
    """Drop InventoryItem rows whose time limit has passed (they are out of play)."""
    return queryset.exclude(expired_at__lte=now or timezone.now())


def exclude_reserved(queryset):
    """
    Drop InventoryItem rows that another system currently holds.

    Equipped items, active market listings and pending trade items are
    reserved. Subqueries are used rather than nullable reverse joins so the
    result stays safe to lock with select_for_update() on stricter databases.
    """
    from apps.characters.models import EquippedItem
    from apps.market.models import Listing, TradeItem

    return (
        queryset
        .exclude(pk__in=EquippedItem.objects.values('item_id'))
        .exclude(pk__in=Listing.objects.filter(is_active=True).values('item_id'))
        .exclude(pk__in=TradeItem.objects.filter(trade__status='pending').values('item_id'))
    )
