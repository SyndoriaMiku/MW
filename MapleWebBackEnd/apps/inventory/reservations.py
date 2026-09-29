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
