from rest_framework import serializers
from .models import ShopCategory, ShopItem, SpecialShopItem, SpecialShopItemRecipe, UserShopPurchase
from apps.items.serializers import ItemTemplateSerializer
from django.utils import timezone

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
            # Cycle logic check to see if it should be reset for display
            if obj.reset_cycle != 'none':
                now = timezone.now()
                last = purchase.last_purchased_at
                if obj.reset_cycle == 'daily':
                    if last.date() < now.date(): return 0
                elif obj.reset_cycle == 'weekly':
                    # isocalendar()[1] gives the week number
                    if last.isocalendar()[1] != now.isocalendar()[1] or last.year != now.year: return 0
                elif obj.reset_cycle == 'monthly':
                    if last.month != now.month or last.year != now.year: return 0
            
            return purchase.quantity_bought
        except UserShopPurchase.DoesNotExist:
            return 0

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
        fields = ['id', 'item', 'is_active', 'recipes']

    def get_recipes(self, obj):
        qs = SpecialShopItemRecipe.objects.filter(recipe=obj)
        return SpecialShopItemRecipeSerializer(qs, many=True).data
