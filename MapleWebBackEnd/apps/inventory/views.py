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
        return self.request.user.character.inventory_items.all()

    @action(detail=True, methods=['post'])
    def equip(self, request, pk=None):
        item = self.get_object()

        if item.is_destroyed:
            return Response({'error': 'Item is destroyed and cannot be equipped.'}, status=status.HTTP_400_BAD_REQUEST)

        character = request.user.character

        if item.expired_at and item.expired_at <= timezone.now():
            return Response({'error': 'Expired items cannot be equipped.'}, status=status.HTTP_400_BAD_REQUEST)
        if character.level < item.template.minimum_level:
            return Response(
                {'error': f'Item requires level {item.template.minimum_level}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            item.template.class_restriction.exists()
            and not item.template.class_restriction.filter(pk=character.character_class_id).exists()
        ):
            return Response({'error': 'Your class cannot equip this item.'}, status=status.HTTP_400_BAD_REQUEST)
        if (
            item.template.job_restriction.exists()
            and not item.template.job_restriction.filter(pk=character.job_id).exists()
        ):
            return Response({'error': 'Your job cannot equip this item.'}, status=status.HTTP_400_BAD_REQUEST)

        # (H-6 fix) Block equip during active combat
        if _character_in_active_battle(character):
            return Response({'error': 'Cannot change equipment while in an active battle.'}, status=status.HTTP_400_BAD_REQUEST)

        # (H-5 fix) Block equip if item is currently listed on market
        from apps.market.models import Listing
        if Listing.objects.filter(item=item, is_active=True).exists():
            return Response({'error': 'Cannot equip an item that is currently listed on the market. Please delist it first.'}, status=status.HTTP_400_BAD_REQUEST)

        # (H-5 fix) Block equip if item is in a pending trade
        from apps.market.models import TradeItem
        if TradeItem.objects.filter(item=item, trade__status='pending').exists():
            return Response({'error': 'Cannot equip an item that is currently in a pending trade.'}, status=status.HTTP_400_BAD_REQUEST)

        item_type = item.template.item_type
        
        # Find config that allows this item_type
        config = None
        for c in EquipmentSlotConfig.objects.all():
            if item_type in c.allowed_item_types:
                config = c
                break
        
        if not config:
            return Response({'error': f'No equipment slot found for item type {item_type}.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            slot_index = int(request.data.get('slot_index', 0))
        except ValueError:
            return Response({'error': 'Invalid slot index.'}, status=status.HTTP_400_BAD_REQUEST)

        if slot_index >= config.max_count or slot_index < 0:
            return Response({'error': f'Invalid slot index. Max count for {config.slot_type} is {config.max_count}.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Lock the item so two equip requests cannot move it concurrently.
            item = InventoryItem.objects.select_for_update().get(pk=item.pk)
            EquippedItem.objects.filter(item=item).delete()
            EquippedItem.objects.filter(
                character=character, slot=config, slot_index=slot_index
            ).delete()
            EquippedItem.objects.create(
                character=character, slot=config, slot_index=slot_index, item=item
            )

        return Response({'status': 'Item equipped successfully.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def unequip(self, request, pk=None):
        item = self.get_object()

        character = request.user.character

        # (H-6 fix) Block unequip during active combat
        if _character_in_active_battle(character):
            return Response({'error': 'Cannot change equipment while in an active battle.'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = EquippedItem.objects.filter(item=item).delete()
        if deleted:
            return Response({'status': 'Item unequipped successfully.'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Item is not equipped.'}, status=status.HTTP_400_BAD_REQUEST)



class EquippedItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EquippedItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'character') or not self.request.user.character:
            from apps.characters.models import EquippedItem
            return EquippedItem.objects.none()
        return self.request.user.character.equipped_items.all()
