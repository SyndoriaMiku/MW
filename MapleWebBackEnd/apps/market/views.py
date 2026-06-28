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
        if item.is_untrade or item.is_destroyed:
            raise serializers.ValidationError("This item cannot be traded.")
        
        # Verify ownership
        if item.owner.user != self.request.user:
            raise serializers.ValidationError("You do not own this item.")

        serializer.save(seller=self.request.user)

    @action(detail=True, methods=['post'])
    def buy(self, request, pk=None):
        listing = self.get_object()
        buyer = request.user

        if listing.seller == buyer:
            return Response({"detail": "You cannot buy your own listing."}, status=status.HTTP_400_BAD_REQUEST)
        
        if buyer.lumis < listing.price:
            return Response({"detail": "Not enough Lumis."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Refresh to avoid race conditions
            listing = Listing.objects.select_for_update().get(pk=listing.pk)
            if not listing.is_active:
                return Response({"detail": "This listing is no longer active."}, status=status.HTTP_400_BAD_REQUEST)
            
            buyer_profile = GameUser.objects.select_for_update().get(pk=buyer.pk)
            seller_profile = GameUser.objects.select_for_update().get(pk=listing.seller.pk)

            # Transfer Lumis
            buyer_profile.lumis -= listing.price
            seller_profile.lumis += listing.price
            buyer_profile.save(update_fields=['lumis'])
            seller_profile.save(update_fields=['lumis'])

            # Transfer Item
            item = listing.item
            item.owner = getattr(buyer, 'character', None)
            
            if item.template.is_trade_once:
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

        serializer.save(sender=self.request.user, receiver=receiver)

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
        if item.is_untrade or item.is_destroyed:
            return Response({"detail": "Item is untradeable."}, status=status.HTTP_400_BAD_REQUEST)

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
        lumis = int(request.data.get('lumis', 0))

        if not role or trade.status != 'pending':
            return Response({"detail": "Invalid state."}, status=status.HTTP_400_BAD_REQUEST)
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
        trade = self.get_object()
        role = self._get_role(trade, request.user)
        
        if not role or trade.status != 'pending':
            return Response({"detail": "Invalid state."}, status=status.HTTP_400_BAD_REQUEST)
        if not trade.sender_ready or not trade.receiver_ready:
            return Response({"detail": "Both parties must be ready to accept."}, status=status.HTTP_400_BAD_REQUEST)

        if role == 'sender': trade.sender_accepted = True
        else: trade.receiver_accepted = True
        trade.save()

        # Execute trade if both accepted
        if trade.sender_accepted and trade.receiver_accepted:
            with transaction.atomic():
                trade = Trade.objects.select_for_update().get(pk=trade.pk)
                sender = GameUser.objects.select_for_update().get(pk=trade.sender.pk)
                receiver = GameUser.objects.select_for_update().get(pk=trade.receiver.pk)

                # Check Lumis again
                if sender.lumis < trade.sender_lumis or receiver.lumis < trade.receiver_lumis:
                    trade.status = 'cancelled'
                    trade.save()
                    return Response({"detail": "Trade cancelled due to insufficient lumis."}, status=status.HTTP_400_BAD_REQUEST)

                # Transfer Lumis
                sender.lumis = sender.lumis - trade.sender_lumis + trade.receiver_lumis
                receiver.lumis = receiver.lumis - trade.receiver_lumis + trade.sender_lumis
                sender.save(update_fields=['lumis'])
                receiver.save(update_fields=['lumis'])

                # Transfer Items
                for ti in trade.items.all():
                    item = ti.item
                    if ti.is_sender:
                        item.owner = getattr(receiver, 'character', None)
                    else:
                        item.owner = getattr(sender, 'character', None)
                        
                    if item.template.is_trade_once:
                        item.is_untrade = True
                        
                    item.save(update_fields=['owner', 'is_untrade'])

                trade.status = 'accepted'
                trade.save()
                return Response({"detail": "Trade successful."})

        return Response({"detail": "Accepted. Waiting for other party."})
