from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import ShopCategory, ShopItem, SpecialShopItem, SpecialShopItemRecipe, UserShopPurchase
from .serializers import (
    ShopCategorySerializer,
    ShopItemSerializer,
    SpecialShopItemSerializer,
    SpecialShopExchangeSerializer,
)
from apps.inventory.models import InventoryItem

class ShopCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing Shop Categories.
    """
    queryset = ShopCategory.objects.all()
    serializer_class = ShopCategorySerializer
    permission_classes = [IsAuthenticated]


class ShopItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and buying normal Shop Items.
    """
    serializer_class = ShopItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ShopItem.objects.select_related('item_template', 'category').all()
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    @action(detail=True, methods=['post'])
    def buy(self, request, pk=None):
        shop_item = self.get_object()
        user = request.user
        character = getattr(user, 'character', None)
        if not character:
            return Response({"detail": "No character found."}, status=status.HTTP_400_BAD_REQUEST)

        quantity = int(request.data.get('quantity', 1))
        if quantity <= 0:
            return Response({"detail": "Invalid quantity."}, status=status.HTTP_400_BAD_REQUEST)

        # Check Category status
        if not shop_item.category.is_active:
            return Response({"detail": "This shop category is not active."}, status=status.HTTP_400_BAD_REQUEST)

        # Check Level
        if character.level < shop_item.required_level:
            return Response({"detail": f"Required level is {shop_item.required_level}."}, status=status.HTTP_400_BAD_REQUEST)

        total_price = shop_item.price * quantity
        currency = shop_item.category.currency_type

        with transaction.atomic():
            # Lock the user profile
            user_profile = user.__class__.objects.select_for_update().get(pk=user.pk)
            
            # Check Currency
            if currency == 'lumis' and user_profile.lumis < total_price:
                return Response({"detail": "Not enough Lumis."}, status=status.HTTP_400_BAD_REQUEST)
            elif currency == 'nova' and user_profile.nova < total_price:
                return Response({"detail": "Not enough Nova."}, status=status.HTTP_400_BAD_REQUEST)

            # Check Stock / Purchase Limit
            if shop_item.stock > 0:
                purchase, created = UserShopPurchase.objects.select_for_update().get_or_create(
                    user=user, shop_item=shop_item, defaults={'quantity_bought': 0}
                )

                now = timezone.now()
                last = purchase.last_purchased_at
                
                # Check Cycle Reset
                if not created and shop_item.reset_cycle != 'none':
                    reset = False
                    if shop_item.reset_cycle == 'daily' and last.date() < now.date(): reset = True
                    elif shop_item.reset_cycle == 'weekly' and (last.isocalendar()[1] != now.isocalendar()[1] or last.year != now.year): reset = True
                    elif shop_item.reset_cycle == 'monthly' and (last.month != now.month or last.year != now.year): reset = True
                    
                    if reset:
                        purchase.quantity_bought = 0

                if purchase.quantity_bought + quantity > shop_item.stock:
                    return Response({
                        "detail": f"Purchase limit exceeded. You can only buy {shop_item.stock - purchase.quantity_bought} more."
                    }, status=status.HTTP_400_BAD_REQUEST)

                purchase.quantity_bought += quantity
                purchase.save()

            # Deduct Currency
            if currency == 'lumis':
                user_profile.lumis -= total_price
                user_profile.save(update_fields=['lumis'])
            elif currency == 'nova':
                user_profile.nova -= total_price
                user_profile.save(update_fields=['nova'])

            # Give Item
            if not shop_item.item_template.is_stackable:
                for _ in range(quantity):
                    InventoryItem.objects.create(
                        template=shop_item.item_template,
                        owner=character,
                        quantity=1
                    )
            else:
                # (B-4 fix) Atomic F() increment prevents quantity race condition
                inv_item, created = InventoryItem.objects.get_or_create(
                    template=shop_item.item_template,
                    owner=character,
                    is_destroyed=False,
                    defaults={'quantity': quantity}
                )
                if not created:
                    InventoryItem.objects.filter(pk=inv_item.pk).update(
                        quantity=F('quantity') + quantity
                    )

        return Response({"detail": f"Successfully purchased {quantity}x {shop_item.item_template.name}."})


class SpecialShopViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Special/Exchange Shop.
    """
    queryset = SpecialShopItem.objects.filter(is_active=True).select_related('item')
    serializer_class = SpecialShopItemSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def exchange(self, request, pk=None):
        special_item = self.get_object()
        character = getattr(request.user, 'character', None)
        if not character:
            return Response({"detail": "No character found."}, status=status.HTTP_400_BAD_REQUEST)

        input_serializer = SpecialShopExchangeSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        quantity = input_serializer.validated_data['quantity']

        recipes = SpecialShopItemRecipe.objects.filter(recipe=special_item)
        if not recipes.exists():
            return Response({"detail": "This item cannot be exchanged."}, status=status.HTTP_400_BAD_REQUEST)

        requirements = [
            {
                'item_template_id': recipe.item_id,
                'quantity': recipe.quantity * quantity,
            }
            for recipe in recipes
        ]

        from apps.inventory.consumption_service import (
            MaterialConsumptionError,
            consume_materials,
        )

        try:
            with transaction.atomic():
                consume_materials(character, requirements)

                # Give the target item only after every material is secured.
                if not special_item.item.is_stackable:
                    for _ in range(quantity):
                        InventoryItem.objects.create(
                            template=special_item.item,
                            owner=character,
                            quantity=1
                        )
                else:
                    new_item, created = InventoryItem.objects.get_or_create(
                        template=special_item.item,
                        owner=character,
                        is_destroyed=False,
                        defaults={'quantity': quantity}
                    )
                    if not created:
                        InventoryItem.objects.filter(pk=new_item.pk).update(
                            quantity=F('quantity') + quantity
                        )
        except MaterialConsumptionError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"detail": f"Successfully exchanged for {quantity}x {special_item.item.name}."})
