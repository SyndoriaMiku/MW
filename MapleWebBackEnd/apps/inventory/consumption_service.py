from collections import defaultdict

from django.db import transaction

from .models import InventoryItem


class MaterialConsumptionError(ValueError):
    """Raised when material requirements are invalid or cannot be fulfilled."""

    def __init__(self, message, *, code='insufficient_materials'):
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_material_requirements(requirements):
    """Validate the shared material shape and reject ambiguous duplicates."""
    if not isinstance(requirements, list) or not requirements:
        raise MaterialConsumptionError(
            'Material requirements must be a non-empty list.',
            code='invalid_material_requirements',
        )

    normalized = {}
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise MaterialConsumptionError(
                f'Material requirement at index {index} must be an object.',
                code='invalid_material_requirements',
            )

        template_id = requirement.get('item_template_id')
        quantity = requirement.get('quantity')
        if isinstance(template_id, bool) or not isinstance(template_id, int) or template_id <= 0:
            raise MaterialConsumptionError(
                f'item_template_id at index {index} must be a positive integer.',
                code='invalid_material_requirements',
            )
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise MaterialConsumptionError(
                f'quantity at index {index} must be a positive integer.',
                code='invalid_material_requirements',
            )
        if template_id in normalized:
            raise MaterialConsumptionError(
                f'Duplicate item_template_id={template_id}.',
                code='invalid_material_requirements',
            )
        normalized[template_id] = quantity

    return normalized


@transaction.atomic
def consume_materials(character, requirements):
    """
    Lock, preflight and then consume every required material as one unit.

    Equipped items, active market listings and pending trade items are reserved
    and never eligible for consumption.
    """
    required_by_template = normalize_material_requirements(requirements)

    # Use subqueries rather than nullable reverse joins. This keeps the locked
    # InventoryItem query portable across databases with stricter FOR UPDATE
    # rules and makes each reservation source explicit.
    from apps.characters.models import EquippedItem
    from apps.market.models import Listing, TradeItem

    equipped_item_ids = EquippedItem.objects.values('item_id')
    listed_item_ids = Listing.objects.filter(is_active=True).values('item_id')
    traded_item_ids = TradeItem.objects.filter(trade__status='pending').values('item_id')

    available_items = list(
        InventoryItem.objects.select_for_update()
        .filter(
            owner=character,
            template_id__in=required_by_template,
            is_destroyed=False,
        )
        .exclude(pk__in=equipped_item_ids)
        .exclude(pk__in=listed_item_ids)
        .exclude(pk__in=traded_item_ids)
        .order_by('template_id', 'quantity', 'id')
    )

    items_by_template = defaultdict(list)
    for inventory_item in available_items:
        items_by_template[inventory_item.template_id].append(inventory_item)

    # Phase 1: validate every requirement before mutating a single row.
    for template_id, quantity_needed in required_by_template.items():
        total_available = sum(item.quantity for item in items_by_template[template_id])
        if total_available < quantity_needed:
            raise MaterialConsumptionError(
                f'Not enough available materials (item_template_id={template_id}).',
            )

    # Phase 2: all requirements are known to be satisfiable under row locks.
    consumed = {}
    for template_id, quantity_needed in required_by_template.items():
        remaining = quantity_needed
        for inventory_item in items_by_template[template_id]:
            if remaining == 0:
                break
            if inventory_item.quantity <= remaining:
                remaining -= inventory_item.quantity
                inventory_item.delete()
            else:
                inventory_item.quantity -= remaining
                inventory_item.save(update_fields=['quantity'])
                remaining = 0
        consumed[template_id] = quantity_needed

    return consumed
