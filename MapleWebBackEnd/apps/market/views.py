from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Case, When, F, FloatField, Q
from django.db import transaction

from .models import Listing, Trade, TradeItem, Transaction as MarketTransaction
from .serializers import ListingSerializer, TradeSerializer
from apps.inventory.models import InventoryItem
from apps.users.models import GameUser

class ListingViewSet(viewsets.ModelViewSet):
    """
    Market Listings ViewSet.
    Allows searching with complex Aurora Line filters.
    """
    serializer_class = ListingSerializer
    permission_classes = [IsAuthenticated]
    # Listings are immutable after creation.  In particular, allowing the
    # ModelViewSet defaults here would let any authenticated user PATCH the
    # item/price of any active listing returned by get_queryset().
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = Listing.objects.filter(is_active=True).select_related('item', 'seller')

        # Filter by name
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(item__template__name__icontains=name)

        # Filter by Lumen / Aurora Level
        min_lumen = self.request.query_params.get('min_lumen')
        if min_lumen is not None:
            queryset = queryset.filter(item__lumen_ascend_level__gte=int(min_lumen))

        min_aurora = self.request.query_params.get('min_aurora')
        if min_aurora is not None:
            queryset = queryset.filter(item__aurora_level__gte=int(min_aurora))

        # Advanced Aurora Stat Filters
        stat_filters = ['str', 'agi', 'int', 'hp', 'mp', 'att', 'drop']
        annotations = {}
        for stat in stat_filters:
            min_stat_pct = self.request.query_params.get(f'min_{stat}_percent')
            if min_stat_pct is not None:
                target_stats = [stat]
                if stat in ['str', 'agi', 'int']:
                    target_stats.append('all')
                
                annotations[f'total_{stat}_pct'] = Sum(
                    Case(
                        When(
                            item__aurora_lines__stat_type__in=target_stats,
                            item__aurora_lines__line_type='percent',
                            then=F('item__aurora_lines__value')
                        ),
                        default=0.0,
                        output_field=FloatField()
                    )
                )

        if annotations:
            queryset = queryset.annotate(**annotations)
            # Filter based on annotations
            for stat in stat_filters:
                min_stat_pct = self.request.query_params.get(f'min_{stat}_percent')
                if min_stat_pct is not None:
                    queryset = queryset.filter(**{f'total_{stat}_pct__gte': float(min_stat_pct)})

        return queryset

    def perform_create(self, serializer):
        item = serializer.validated_data['item']
        # Prevent listing untradeable items
        if not item.template.is_tradeable or item.is_untrade or item.is_destroyed:
            raise serializers.ValidationError("This item cannot be traded.")

        price = serializer.validated_data['price']
        quantity = serializer.validated_data.get('quantity', 1)
        if price <= 0:
            raise serializers.ValidationError({"price": "Price must be greater than zero."})
        if quantity <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
        if item.template.is_stackable:
            if quantity > item.quantity:
                raise serializers.ValidationError({"quantity": "Quantity exceeds the owned stack."})
        elif quantity != 1:
            raise serializers.ValidationError({"quantity": "Equipment listings must have quantity 1."})
        
        # Verify ownership
        if item.owner.user != self.request.user:
            raise serializers.ValidationError("You do not own this item.")

        # (RC-6 fix) Prevent listing items that are currently equipped
        if hasattr(item, 'equipped_in') and item.equipped_in is not None:
            raise serializers.ValidationError("Cannot list an item that is currently equipped. Please unequip it first.")

        # (C-5 fix) Prevent listing the same item multiple times
        if Listing.objects.filter(item=item, is_active=True).exists():
            raise serializers.ValidationError("This item is already listed on the market.")
        if TradeItem.objects.filter(item=item, trade__status='pending').exists():
            raise serializers.ValidationError("An item in a pending trade cannot be listed.")

        serializer.save(seller=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Only the seller may cancel a listing; keep the row for audit/history."""
        listing = self.get_object()
        if listing.seller_id != request.user.pk:
            return Response(
                {"detail": "You may only cancel your own listing."},
                status=status.HTTP_403_FORBIDDEN,
            )
        listing.is_active = False
        listing.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def buy(self, request, pk=None):
        listing = self.get_object()
        buyer = request.user

        if listing.seller == buyer:
            return Response({"detail": "You cannot buy your own listing."}, status=status.HTTP_400_BAD_REQUEST)
        buyer_character = getattr(buyer, 'character', None)
        if buyer_character is None:
            return Response({"detail": "Create a character before buying items."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fast-fail before entering lock (stale check is fine here for UX)
        if buyer.lumis < listing.price:
            return Response({"detail": "Not enough Lumis."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Refresh to avoid race conditions
            listing = Listing.objects.select_for_update().get(pk=listing.pk)
            if not listing.is_active:
                return Response({"detail": "This listing is no longer active."}, status=status.HTTP_400_BAD_REQUEST)

            item = InventoryItem.objects.select_for_update().select_related(
                'template', 'owner__user'
            ).get(pk=listing.item_id)
            owner_user = getattr(item.owner, 'user', None)
            if owner_user is None or owner_user.pk != listing.seller_id or item.is_destroyed or item.is_untrade:
                listing.is_active = False
                listing.save(update_fields=['is_active'])
                return Response({"detail": "This listing is no longer valid."}, status=status.HTTP_400_BAD_REQUEST)
            if listing.quantity <= 0 or listing.quantity > item.quantity:
                listing.is_active = False
                listing.save(update_fields=['is_active'])
                return Response({"detail": "The listed quantity is no longer available."}, status=status.HTTP_400_BAD_REQUEST)
            
            # (H-4 fix) Lock users in ascending PK order to prevent deadlock
            user_pks = sorted([buyer.pk, listing.seller.pk])
            locked_users = {
                u.pk: u
                for u in GameUser.objects.select_for_update().filter(pk__in=user_pks).order_by('pk')
            }
            buyer_profile = locked_users[buyer.pk]
            seller_profile = locked_users[listing.seller.pk]

            # (C-4 fix) Re-check balance UNDER lock — prevents concurrent buy going negative
            if buyer_profile.lumis < listing.price:
                return Response({"detail": "Not enough Lumis."}, status=status.HTTP_400_BAD_REQUEST)

            # Transfer Lumis
            buyer_profile.lumis -= listing.price
            seller_profile.lumis += listing.price
            buyer_profile.save(update_fields=['lumis'])
            seller_profile.save(update_fields=['lumis'])


            # Transfer either the whole inventory row or a split from a
            # stackable row.  The listing price is the price for the listed
            # quantity as a whole.
            becomes_untradeable = item.template.is_trade_once
            if item.template.is_stackable and listing.quantity < item.quantity:
                item.quantity -= listing.quantity
                item.save(update_fields=['quantity'])
                InventoryItem.objects.create(
                    template=item.template,
                    owner=buyer_character,
                    quantity=listing.quantity,
                    is_untrade=becomes_untradeable,
                )
            else:
                item.owner = buyer_character
                if becomes_untradeable:
                    item.is_untrade = True
                item.save(update_fields=['owner', 'is_untrade'])

            # Complete transaction
            listing.is_active = False
            listing.save(update_fields=['is_active'])

            MarketTransaction.objects.create(
                listing=listing,
                buyer=buyer,
                seller=listing.seller
            )

        return Response({"detail": "Item purchased successfully."})



class TradeViewSet(viewsets.ModelViewSet):
    """
    P2P Trading ViewSet.
    """
    serializer_class = TradeSerializer
    permission_classes = [IsAuthenticated]
    # Trade offers may only change through the explicit actions below.  This
    # prevents generic PATCH from changing both parties' Lumis or trade state.
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        return Trade.objects.filter(Q(sender=user) | Q(receiver=user))

    def perform_create(self, serializer):
        receiver_id = serializer.validated_data.pop('receiver_id', None)
        if not receiver_id:
            raise serializers.ValidationError({"receiver_id": "Required."})
        
        try:
            receiver = GameUser.objects.get(pk=receiver_id)
        except GameUser.DoesNotExist:
            raise serializers.ValidationError({"receiver_id": "Receiver not found."})
        
        if receiver == self.request.user:
            raise serializers.ValidationError({"receiver_id": "Cannot trade with yourself."})

        serializer.save(
            sender=self.request.user,
            receiver=receiver,
            sender_lumis=0,
            receiver_lumis=0,
        )

    def _get_role(self, trade, user):
        if trade.sender == user: return 'sender'
        if trade.receiver == user: return 'receiver'
        return None

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        trade = self.get_object()
        user = request.user
        role = self._get_role(trade, user)

        if not role:
            return Response({"detail": "Not a participant in this trade."}, status=status.HTTP_403_FORBIDDEN)
        if trade.status != 'pending':
            return Response({"detail": "Trade is not pending."}, status=status.HTTP_400_BAD_REQUEST)
        
        # If ready, cannot modify
        if (role == 'sender' and trade.sender_ready) or (role == 'receiver' and trade.receiver_ready):
            return Response({"detail": "Cannot modify items while ready."}, status=status.HTTP_400_BAD_REQUEST)

        item_id = request.data.get('item_id')
        try:
            item = InventoryItem.objects.get(pk=item_id)
        except InventoryItem.DoesNotExist:
            return Response({"detail": "Item not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if getattr(item.owner, 'user', None) != user:
            return Response({"detail": "You do not own this item."}, status=status.HTTP_400_BAD_REQUEST)
        if not item.template.is_tradeable or item.is_untrade or item.is_destroyed:
            return Response({"detail": "Item is untradeable."}, status=status.HTTP_400_BAD_REQUEST)

        if hasattr(item, 'equipped_in'):
            return Response({"detail": "Equipped items cannot be traded."}, status=status.HTTP_400_BAD_REQUEST)
        if Listing.objects.filter(item=item, is_active=True).exists():
            return Response({"detail": "Listed items cannot be added to a trade."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure item not already in trade
        if TradeItem.objects.filter(item=item).exists():
            return Response({"detail": "Item is already in a trade."}, status=status.HTTP_400_BAD_REQUEST)

        TradeItem.objects.create(trade=trade, item=item, is_sender=(role == 'sender'))
        
        # Un-ready the other party
        if role == 'sender':
            trade.receiver_ready = False
            trade.receiver_accepted = False
        else:
            trade.sender_ready = False
            trade.sender_accepted = False
        trade.save()

        return Response({"detail": "Item added."})

    @action(detail=True, methods=['post'])
    def update_lumis(self, request, pk=None):
        trade = self.get_object()
        user = request.user
        role = self._get_role(trade, user)
        try:
            lumis = int(request.data.get('lumis', 0))
        except (TypeError, ValueError):
            return Response({"detail": "Lumis must be a non-negative integer."}, status=status.HTTP_400_BAD_REQUEST)

        if not role or trade.status != 'pending':
            return Response({"detail": "Invalid state."}, status=status.HTTP_400_BAD_REQUEST)
        if lumis < 0:
            return Response({"detail": "Lumis must be a non-negative integer."}, status=status.HTTP_400_BAD_REQUEST)
        if (role == 'sender' and trade.sender_ready) or (role == 'receiver' and trade.receiver_ready):
            return Response({"detail": "Cannot modify lumis while ready."}, status=status.HTTP_400_BAD_REQUEST)
        if user.lumis < lumis:
            return Response({"detail": "Not enough Lumis."}, status=status.HTTP_400_BAD_REQUEST)

        if role == 'sender':
            trade.sender_lumis = lumis
            trade.receiver_ready = False
            trade.receiver_accepted = False
        else:
            trade.receiver_lumis = lumis
            trade.sender_ready = False
            trade.sender_accepted = False
        trade.save()
        return Response({"detail": "Lumis updated."})

    @action(detail=True, methods=['post'])
    def ready(self, request, pk=None):
        trade = self.get_object()
        role = self._get_role(trade, request.user)
        
        if not role or trade.status != 'pending':
            return Response({"detail": "Invalid state."}, status=status.HTTP_400_BAD_REQUEST)

        if role == 'sender':
            trade.sender_ready = not trade.sender_ready
            if not trade.sender_ready: trade.sender_accepted = False
        else:
            trade.receiver_ready = not trade.receiver_ready
            if not trade.receiver_ready: trade.receiver_accepted = False
            
        trade.save()
        return Response({"detail": "Ready state updated."})

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        # (TS-3 fix) Entire accept logic must be atomic with row lock
        with transaction.atomic():
            trade = Trade.objects.select_for_update().get(pk=pk)
            role = self._get_role(trade, request.user)
            
            if not role or trade.status != 'pending':
                return Response({"detail": "Invalid state."}, status=status.HTTP_400_BAD_REQUEST)
            if not trade.sender_ready or not trade.receiver_ready:
                return Response({"detail": "Both parties must be ready to accept."}, status=status.HTTP_400_BAD_REQUEST)

            if role == 'sender': trade.sender_accepted = True
            else: trade.receiver_accepted = True
            trade.save(update_fields=['sender_accepted', 'receiver_accepted'])

            # Execute trade if both accepted
            if trade.sender_accepted and trade.receiver_accepted:
                # (H-4 fix) Always lock users in ascending PK order to prevent deadlock.
                # If A locks A→B while B locks B→A, they deadlock. Sorted order eliminates this.
                user_pks = sorted([trade.sender.pk, trade.receiver.pk])
                locked_users = {
                    u.pk: u
                    for u in GameUser.objects.select_for_update().filter(pk__in=user_pks).order_by('pk')
                }
                sender = locked_users[trade.sender.pk]
                receiver = locked_users[trade.receiver.pk]

                sender_character = getattr(sender, 'character', None)
                receiver_character = getattr(receiver, 'character', None)
                if sender_character is None or receiver_character is None:
                    return Response(
                        {"detail": "Both participants must have a character."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                trade_items = list(
                    TradeItem.objects.select_for_update().select_related(
                        'item__template', 'item__owner__user'
                    ).filter(trade=trade)
                )
                for trade_item in trade_items:
                    item = trade_item.item
                    expected_owner = sender if trade_item.is_sender else receiver
                    actual_owner = getattr(item.owner, 'user', None)
                    invalid_item = (
                        actual_owner is None
                        or actual_owner.pk != expected_owner.pk
                        or item.is_destroyed
                        or item.is_untrade
                        or not item.template.is_tradeable
                        or hasattr(item, 'equipped_in')
                        or Listing.objects.filter(item=item, is_active=True).exists()
                    )
                    if invalid_item:
                        trade.status = 'cancelled'
                        trade.save(update_fields=['status'])
                        return Response(
                            {"detail": "Trade cancelled because an offered item is no longer valid."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Check Lumis again
                if sender.lumis < trade.sender_lumis or receiver.lumis < trade.receiver_lumis:
                    trade.status = 'cancelled'
                    trade.save(update_fields=['status'])
                    return Response({"detail": "Trade cancelled due to insufficient lumis."}, status=status.HTTP_400_BAD_REQUEST)


                # Transfer Lumis
                sender.lumis = sender.lumis - trade.sender_lumis + trade.receiver_lumis
                receiver.lumis = receiver.lumis - trade.receiver_lumis + trade.sender_lumis
                sender.save(update_fields=['lumis'])
                receiver.save(update_fields=['lumis'])

                # Transfer Items
                for ti in trade_items:
                    item = ti.item
                    if ti.is_sender:
                        item.owner = receiver_character
                    else:
                        item.owner = sender_character
                        
                    if item.template.is_trade_once:
                        item.is_untrade = True
                        
                    item.save(update_fields=['owner', 'is_untrade'])

                trade.status = 'accepted'
                trade.save(update_fields=['status'])
                return Response({"detail": "Trade successful."})

        return Response({"detail": "Accepted. Waiting for other party."})
