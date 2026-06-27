from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import InventoryItem
from apps.characters.models import EquippedItem, EquipmentSlotConfig
from .serializers import InventoryItemSerializer, EquippedItemSerializer

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
            
        character = request.user.character

        # Remove item if equipped elsewhere
        EquippedItem.objects.filter(item=item).delete()
        
        # Remove any item currently in the target slot
        EquippedItem.objects.filter(character=character, slot=config, slot_index=slot_index).delete()

        # Equip
        EquippedItem.objects.create(character=character, slot=config, slot_index=slot_index, item=item)

        return Response({'status': 'Item equipped successfully.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def unequip(self, request, pk=None):
        item = self.get_object()
        
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
