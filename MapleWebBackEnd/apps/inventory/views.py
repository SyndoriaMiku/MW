from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from .models import AuroraLine, InventoryItem, SoldItem
from .reservations import character_in_active_battle, exclude_expired, exclude_reserved
from apps.request_params import parse_int
from apps.characters.models import EquippedItem, EquipmentSlotConfig, Character
from .serializers import (
    EquipmentSlotConfigSerializer, EquippedItemSerializer, InventoryItemSerializer, SoldItemSerializer,
)


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'character') or not self.request.user.character:
            return InventoryItem.objects.none()
        # Expired items are out of play until purge_expired_items deletes them.
        return exclude_expired(self.request.user.character.inventory_items).select_related(
            'template__lumen_tier', 'template__aurora_tier'
        ).prefetch_related(
            'aurora_lines',
            'template__lumen_tier__ascend_rules',
            'template__item_sets__effects',
            'template__item_sets__items',
        ).order_by('id')

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
            # Each job uses one weapon type (no job, or a job not set up yet, uses any).
            job_weapon_type = character.job.weapon_type if character.job_id else None
            if (
                item.template.item_type == 'weapon'
                and job_weapon_type
                and item.template.weapon_type != job_weapon_type
            ):
                return Response(
                    {'error': f'Your job can only equip {character.job.get_weapon_type_display()} weapons.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if character_in_active_battle(character):
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

            if character_in_active_battle(character):
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

    @action(detail=True, methods=['post'])
    def sell(self, request, pk=None):
        """Sell `quantity` (default 1) of an item to the NPC for its sell_price each."""
        if not request.user.character_id:
            return Response({'error': 'Create a character first.'}, status=status.HTTP_400_BAD_REQUEST)
        quantity = parse_int(request.data.get('quantity', 1), 'quantity', min_value=1)
        if quantity is None:
            quantity = 1

        from apps.users.models import GameUser

        with transaction.atomic():
            user = GameUser.objects.select_for_update().get(pk=request.user.pk)
            try:
                item = InventoryItem.objects.select_for_update().select_related('template').get(
                    pk=pk, owner_id=request.user.character_id
                )
            except InventoryItem.DoesNotExist:
                return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

            if not item.template.is_sellable:
                return Response({'error': 'This item cannot be sold.'}, status=status.HTTP_400_BAD_REQUEST)
            if hasattr(item, 'equipped_in'):
                return Response({'error': 'Unequip the item before selling it.'}, status=status.HTTP_400_BAD_REQUEST)
            if not exclude_reserved(InventoryItem.objects.filter(pk=item.pk)).exists():
                return Response(
                    {'error': 'Items listed on the market or offered in a trade cannot be sold.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if item.is_destroyed:
                return Response({'error': 'Destroyed items cannot be sold.'}, status=status.HTTP_400_BAD_REQUEST)
            if item.expired_at and item.expired_at <= timezone.now():
                return Response({'error': 'Expired items cannot be sold.'}, status=status.HTTP_400_BAD_REQUEST)
            if quantity > item.quantity or (not item.template.is_stackable and quantity != 1):
                return Response({'error': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
            if hasattr(item, 'pending_aurora_roll'):
                # Buy back restores the item, not an unconfirmed roll on it.
                return Response(
                    {'error': 'Keep or take the pending Aurora roll before selling this item.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lumis_gained = max(0, item.template.sell_price) * quantity
            sold = SoldItem.objects.create(
                owner_id=request.user.character_id,
                template=item.template,
                quantity=quantity,
                price=lumis_gained,
                lumen_ascend_level=item.lumen_ascend_level,
                aurora_level=item.aurora_level,
                aurora_lines=[
                    {
                        'line_index': line.line_index, 'stat_type': line.stat_type,
                        'line_type': line.line_type, 'value': line.value,
                    }
                    for line in item.aurora_lines.order_by('line_index')
                ],
                is_untrade=item.is_untrade,
                expired_at=item.expired_at,
            )
            outdated = list(
                SoldItem.objects.filter(owner_id=request.user.character_id)
                .values_list('pk', flat=True)[SoldItem.BUYBACK_LIMIT:]
            )
            SoldItem.objects.filter(pk__in=outdated).delete()
            if quantity == item.quantity:
                item.delete()
            else:
                item.quantity -= quantity
                item.save(update_fields=['quantity'])
            user.lumis += lumis_gained
            user.save(update_fields=['lumis'])

        return Response({
            'status': 'Item sold.',
            'lumis_gained': lumis_gained,
            'lumis': user.lumis,
            'buyback_id': sold.pk,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """Use one timed buff item (e.g. an x2 EXP charm) outside battle."""
        if not request.user.character_id:
            return Response({'error': 'Create a character first.'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.characters.buff_service import BuffError, use_buff_item
        from apps.characters.serializers import CharacterBuffSerializer

        try:
            buff, remaining_quantity = use_buff_item(request.user.character_id, pk)
        except InventoryItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)
        except BuffError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status': 'Buff applied.',
            'buff': CharacterBuffSerializer(buff).data,
            'remaining_quantity': remaining_quantity,
        }, status=status.HTTP_200_OK)



class BuybackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/inventory/buyback/                  -> the caller's latest sales, newest first
    POST /api/inventory/buyback/{id}/repurchase/  -> buy one back for the price it sold for
    """
    serializer_class = SoldItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SoldItem.objects.none()
        return SoldItem.objects.filter(owner_id=self.request.user.character_id).select_related('template')

    @action(detail=True, methods=['post'])
    def repurchase(self, request, pk=None):
        if not request.user.character_id:
            return Response({'error': 'Create a character first.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.users.models import GameUser
        from .grant_service import grant_item

        with transaction.atomic():
            user = GameUser.objects.select_for_update().get(pk=request.user.pk)
            try:
                sold = SoldItem.objects.select_for_update(of=('self',)).select_related('template').get(
                    pk=pk, owner_id=user.character_id
                )
            except SoldItem.DoesNotExist:
                return Response({'error': 'This item can no longer be bought back.'}, status=status.HTTP_404_NOT_FOUND)
            if sold.expired_at and sold.expired_at <= timezone.now():
                return Response({'error': 'This item has expired and cannot be bought back.'}, status=status.HTTP_400_BAD_REQUEST)
            if user.lumis < sold.price:
                return Response({'error': 'Not enough Lumis.'}, status=status.HTTP_400_BAD_REQUEST)

            character = Character.objects.get(pk=user.character_id)
            item = grant_item(
                character, sold.template, sold.quantity,
                is_untrade=sold.is_untrade, expired_at=sold.expired_at,
            )[0]
            if not sold.template.is_stackable:
                item.lumen_ascend_level = sold.lumen_ascend_level
                item.aurora_level = sold.aurora_level
                item.save(update_fields=['lumen_ascend_level', 'aurora_level'])
                AuroraLine.objects.bulk_create(
                    AuroraLine(inventory_item=item, **line) for line in sold.aurora_lines
                )
            user.lumis -= sold.price
            user.save(update_fields=['lumis'])
            sold.delete()

        return Response({
            'status': 'Item bought back.',
            'lumis': user.lumis,
            'item': InventoryItemSerializer(item).data,
        }, status=status.HTTP_200_OK)


class EquippedItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EquippedItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'character') or not self.request.user.character:
            from apps.characters.models import EquippedItem
            return EquippedItem.objects.none()
        return self.request.user.character.equipped_items.exclude(
            item__expired_at__lte=timezone.now(),
        ).select_related(
            'item__template__lumen_tier', 'item__template__aurora_tier'
        ).prefetch_related(
            'item__aurora_lines',
            'item__template__lumen_tier__ascend_rules',
            'item__template__item_sets__effects',
            'item__template__item_sets__items',
        )


class EquipmentSlotConfigViewSet(viewsets.ReadOnlyModelViewSet):
    """Equipment slots the client lays out: type, capacity and accepted item types."""
    queryset = EquipmentSlotConfig.objects.all()
    serializer_class = EquipmentSlotConfigSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
