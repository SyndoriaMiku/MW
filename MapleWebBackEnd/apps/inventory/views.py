from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .models import InventoryItem
from apps.characters.models import EquippedItem, EquipmentSlotConfig, Character
from .serializers import InventoryItemSerializer, EquippedItemSerializer


def _character_in_active_battle(character):
    """Return True if the character is currently in an in-progress combat."""
    from apps.battles.models import Combatant
    ct = ContentType.objects.get_for_model(character)
    return Combatant.objects.filter(
        content_type=ct,
        objects_id=str(character.id),
        combat_instance__status='in_progress'
    ).exists()


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'character') or not self.request.user.character:
            return InventoryItem.objects.none()
        return self.request.user.character.inventory_items.select_related(
            'template__lumen_tier', 'template__aurora_tier'
        ).prefetch_related(
            'aurora_lines',
            'template__lumen_tier__ascend_rules',
            'template__item_sets__effects',
            'template__item_sets__items',
        )

    @action(detail=True, methods=['post'])
    def equip(self, request, pk=None):
        if not request.user.character_id:
            return Response({'error': 'Create a character first.'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.market.models import Listing
        from apps.market.models import TradeItem

        try:
            slot_index = int(request.data.get('slot_index', 0))
        except (TypeError, ValueError):
            return Response({'error': 'Invalid slot index.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            character = Character.objects.select_for_update().get(pk=request.user.character_id)
            try:
                item = InventoryItem.objects.select_for_update().select_related(
                    'template'
                ).get(pk=pk, owner=character)
            except InventoryItem.DoesNotExist:
                return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

            if item.is_destroyed:
                return Response({'error': 'Item is destroyed and cannot be equipped.'}, status=status.HTTP_400_BAD_REQUEST)
            if item.expired_at and item.expired_at <= timezone.now():
                return Response({'error': 'Expired items cannot be equipped.'}, status=status.HTTP_400_BAD_REQUEST)
            if character.level < item.template.minimum_level:
                return Response(
                    {'error': f'Item requires level {item.template.minimum_level}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (
                item.template.class_restriction.exists()
                and not item.template.class_restriction.filter(
                    pk=character.character_class_id
                ).exists()
            ):
                return Response({'error': 'Your class cannot equip this item.'}, status=status.HTTP_400_BAD_REQUEST)
            if (
                item.template.job_restriction.exists()
                and not item.template.job_restriction.filter(pk=character.job_id).exists()
            ):
                return Response({'error': 'Your job cannot equip this item.'}, status=status.HTTP_400_BAD_REQUEST)
            if _character_in_active_battle(character):
                return Response({'error': 'Cannot change equipment while in an active battle.'}, status=status.HTTP_400_BAD_REQUEST)
            if Listing.objects.filter(item=item, is_active=True).exists():
                return Response(
                    {'error': 'Cannot equip an item that is currently listed on the market. Please delist it first.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if TradeItem.objects.filter(item=item, trade__status='pending').exists():
                return Response(
                    {'error': 'Cannot equip an item that is currently in a pending trade.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            config = next(
                (
                    candidate for candidate in EquipmentSlotConfig.objects.all()
                    if item.template.item_type in candidate.allowed_item_types
                ),
                None,
            )
            if not config:
                return Response(
                    {'error': f'No equipment slot found for item type {item.template.item_type}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if slot_index >= config.max_count or slot_index < 0:
                return Response(
                    {'error': f'Invalid slot index. Max count for {config.slot_type} is {config.max_count}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            occupied = EquippedItem.objects.select_for_update().filter(
                character=character, slot=config, slot_index=slot_index
            ).first()
            replaced_item_id = (
                occupied.item_id if occupied and occupied.item_id != item.id else None
            )
            EquippedItem.objects.filter(item=item).delete()
            EquippedItem.objects.filter(
                character=character, slot=config, slot_index=slot_index
            ).delete()
            equipped = EquippedItem.objects.create(
                character=character, slot=config, slot_index=slot_index, item=item
            )

        return Response({
            'status': 'Item equipped successfully.',
            'equipped': EquippedItemSerializer(equipped).data,
            'replaced_item_id': replaced_item_id,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def unequip(self, request, pk=None):
        if not request.user.character_id:
            return Response({'error': 'Create a character first.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            character = Character.objects.select_for_update().get(pk=request.user.character_id)
            try:
                item = InventoryItem.objects.select_for_update().get(pk=pk, owner=character)
            except InventoryItem.DoesNotExist:
                return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

            if _character_in_active_battle(character):
                return Response({'error': 'Cannot change equipment while in an active battle.'}, status=status.HTTP_400_BAD_REQUEST)

            equipped = EquippedItem.objects.select_for_update().filter(
                character=character, item=item
            ).first()
            if not equipped:
                return Response({'error': 'Item is not equipped.'}, status=status.HTTP_400_BAD_REQUEST)
            equipped.delete()

        return Response({
            'status': 'Item unequipped successfully.',
            'item': InventoryItemSerializer(item).data,
        }, status=status.HTTP_200_OK)



class EquippedItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EquippedItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'character') or not self.request.user.character:
            from apps.characters.models import EquippedItem
            return EquippedItem.objects.none()
        return self.request.user.character.equipped_items.select_related(
            'item__template__lumen_tier', 'item__template__aurora_tier'
        ).prefetch_related(
            'item__aurora_lines',
            'item__template__lumen_tier__ascend_rules',
            'item__template__item_sets__effects',
            'item__template__item_sets__items',
        )
