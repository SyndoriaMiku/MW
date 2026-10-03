from django.db import transaction
from django.db.models import F

from .models import InventoryItem
from .reservations import exclude_reserved


# Default for grant_item(expired_at=...): the template's time limit for a new copy.
TEMPLATE_EXPIRY = object()


@transaction.atomic
def grant_item(character, template, quantity, *, is_untrade=False, expired_at=TEMPLATE_EXPIRY):
    """
    Give `quantity` of `template` to `character` and return the touched rows.

    Copies get the template's time limit (ItemTemplate.new_copy_expiry) unless
    `expired_at` is given, e.g. to give back a sold item with its old expiry.
    Equipment always gets one row per copy. Stackable items merge into the
    oldest free stack with the same tradeability and the same expiry; a
    character may legitimately own several stacks (market splits, trades),
    so this never assumes there is only one. Reserved or destroyed stacks are
    never merged into: doing so would move the new items with a trade or hide
    them from material consumption. Items with a relative limit therefore get
    a stack per grant, while a fixed event expiry lets them stack.
    """
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValueError('quantity must be a positive integer.')

    if expired_at is TEMPLATE_EXPIRY:
        expired_at = template.new_copy_expiry()

    if not template.is_stackable:
        return [
            InventoryItem.objects.create(
                template=template, owner=character, quantity=1, is_untrade=is_untrade,
                expired_at=expired_at,
            )
            for _ in range(quantity)
        ]

    stack = exclude_reserved(
        InventoryItem.objects.select_for_update().filter(
            owner=character,
            template=template,
            is_destroyed=False,
            is_untrade=is_untrade,
            expired_at=expired_at,
        )
    ).order_by('id').first()

    if stack is None:
        return [
            InventoryItem.objects.create(
                template=template, owner=character, quantity=quantity, is_untrade=is_untrade,
                expired_at=expired_at,
            )
        ]

    InventoryItem.objects.filter(pk=stack.pk).update(quantity=F('quantity') + quantity)
    stack.refresh_from_db(fields=['quantity'])
    return [stack]
