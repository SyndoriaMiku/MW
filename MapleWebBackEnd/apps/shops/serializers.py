from rest_framework import serializers
from .models import ShopCategory, ShopItem, SpecialShop, SpecialShopItem, SpecialShopItemRecipe, UserShopPurchase
from apps.items.serializers import ItemTemplateSerializer
from apps.reset_cycles import is_current_period

class ShopCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopCategory
        fields = ['id', 'name', 'order', 'currency_type', 'required_level', 'start_date', 'end_date', 'is_active', 'is_event']

class ShopItemSerializer(serializers.ModelSerializer):
    item_template = ItemTemplateSerializer(read_only=True)
    current_bought = serializers.SerializerMethodField()

    class Meta:
        model = ShopItem
        fields = ['id', 'category', 'item_template', 'price', 'stock', 'reset_cycle', 'order', 'required_level', 'current_bought']

    def get_current_bought(self, obj):
        user = self.context.get('request').user
        if not user or not user.is_authenticated:
            return 0
        try:
            purchase = UserShopPurchase.objects.get(user=user, shop_item=obj)
        except UserShopPurchase.DoesNotExist:
            return 0
        # Same reset calendar as the purchase limit in ShopItemViewSet.buy.
        if obj.reset_cycle != 'none' and not is_current_period(purchase.last_purchased_at, obj.reset_cycle):
            return 0
        return purchase.quantity_bought

class SpecialShopItemRecipeSerializer(serializers.ModelSerializer):
    item = ItemTemplateSerializer(read_only=True)

    class Meta:
        model = SpecialShopItemRecipe
        fields = ['item', 'quantity']

class SpecialShopItemSerializer(serializers.ModelSerializer):
    item = ItemTemplateSerializer(read_only=True)
    recipes = serializers.SerializerMethodField()

    class Meta:
        model = SpecialShopItem
        fields = ['id', 'shop', 'item', 'is_active', 'recipes']

    def get_recipes(self, obj):
        qs = SpecialShopItemRecipe.objects.filter(recipe=obj)
        return SpecialShopItemRecipeSerializer(qs, many=True).data


class SpecialShopSerializer(serializers.ModelSerializer):
    """An open exchange shop; is_event shops close at end_time."""
    items = SpecialShopItemSerializer(many=True, read_only=True)
    is_event = serializers.BooleanField(read_only=True)

    class Meta:
        model = SpecialShop
        fields = [
            'id', 'name', 'description', 'order', 'required_level',
            'is_event', 'start_time', 'end_time', 'items',
        ]


# Equipment is granted one row per copy, so an unbounded quantity could create
# an unbounded number of rows in one request.
MAX_QUANTITY_PER_REQUEST = 999


class ShopPurchaseSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_REQUEST, default=1)


class SpecialShopExchangeSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_REQUEST, default=1)
