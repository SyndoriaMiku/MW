from django.db import transaction
from django.db.models import F

from .models import InventoryItem
from .reservations import exclude_reserved


@transaction.atomic
def grant_item(character, template, quantity, *, is_untrade=False):
    """
    Give `quantity` of `template` to `character` and return the touched rows.

    Equipment always gets one row per copy. Stackable items merge into the
    oldest free stack with the same tradeability; a character may legitimately
    own several stacks (market splits, trades), so this never assumes there is
    only one. Reserved, destroyed or expiring stacks are never merged into:
    doing so would move the new items with a trade, hide them from material
    consumption, or make them expire.
    """
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError('quantity must be a positive integer.')

    if not template.is_stackable:
        return [
            InventoryItem.objects.create(
                template=template, owner=character, quantity=1, is_untrade=is_untrade,
            )
            for _ in range(quantity)
        ]

    stack = exclude_reserved(
        InventoryItem.objects.select_for_update().filter(
            owner=character,
            template=template,
            is_destroyed=False,
            is_untrade=is_untrade,
            expired_at__isnull=True,
        )
    ).order_by('id').first()

    if stack is None:
        return [
            InventoryItem.objects.create(
                template=template, owner=character, quantity=quantity, is_untrade=is_untrade,
            )
        ]

    InventoryItem.objects.filter(pk=stack.pk).update(quantity=F('quantity') + quantity)
    stack.refresh_from_db(fields=['quantity'])
    return [stack]
