from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class ShopCategory(models.Model):
    class CurrencyType(models.TextChoices):
        LUMIS = 'lumis', 'Lumis'
        NOVA = 'nova', 'Nova'    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    # Currency type
    currency_type = models.CharField(max_length=10, choices=CurrencyType.choices, default=CurrencyType.LUMIS)

    # Requirement
    required_level = models.PositiveIntegerField(default=1, help_text="Minimum level required to access this category")

    start_date = models.DateTimeField(null=True, blank=True, help_text="Null means always available")
    end_date = models.DateTimeField(null=True, blank=True, help_text="Null means always available")

    @property
    def is_event(self):
        return self.start_date is not None and self.end_date is not None
    
    @property
    def is_active(self):
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    class Meta:
        verbose_name = "Shop Category"
        verbose_name_plural = "Shop Categories"
        ordering = ['order']
    def __str__(self):
        return self.name
    
class ShopItem(models.Model):
    class ResetCycle(models.TextChoices):
        NONE = 'none', 'None (Lifetime)'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    id = models.AutoField(primary_key=True)
    category = models.ForeignKey('shops.ShopCategory', on_delete=models.CASCADE, related_name='shop_items')
    item_template = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE)
    price = models.PositiveBigIntegerField(default=0)
    stock = models.PositiveIntegerField(default=0, help_text="0 means unlimited stock per user per cycle")
    reset_cycle = models.CharField(max_length=10, choices=ResetCycle.choices, default=ResetCycle.NONE)
    order = models.PositiveIntegerField(default=0)

    # Requirement
    required_level = models.PositiveIntegerField(default=1, help_text="Minimum level required to purchase this item")

    def clean(self):
        # Ensure the item's category is active
        if self.price < 0:
            raise ValidationError('Price cannot be negative')
        if self.stock < 0:
            raise ValidationError('Stock cannot be negative')
        if self.item_template is None:
            raise ValidationError('Item template must be set')
        if self.category is None:
            raise ValidationError('Category must be set')
        if self.required_level < self.category.required_level:
            raise ValidationError('Item required level cannot be lower than category required level')

    class Meta:
        verbose_name = "Shop Item"
        verbose_name_plural = "Shop Items"
        ordering = ['order']
    def __str__(self):
        return f"{self.item_template.name} in {self.category.name} for {self.price} {self.category.currency_type}"

class UserShopPurchase(models.Model):
    user = models.ForeignKey('users.GameUser', on_delete=models.CASCADE, related_name='shop_purchases')
    shop_item = models.ForeignKey('shops.ShopItem', on_delete=models.CASCADE)
    quantity_bought = models.PositiveIntegerField(default=0)
    last_purchased_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Shop Purchase"
        verbose_name_plural = "User Shop Purchases"
        unique_together = ('user', 'shop_item')

    def __str__(self):
        return f"{self.user.username} bought {self.quantity_bought} of {self.shop_item.item_template.name}"

class SpecialShop(models.Model):
    """
    An exchange shop (items for materials). With no start/end time it is
    permanent; with them it is an event shop, open only in that window.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Switch the shop off without deleting it")
    required_level = models.PositiveIntegerField(default=1)
    start_time = models.DateTimeField(null=True, blank=True, help_text="Empty = open from now")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Empty = never closes")

    class Meta:
        verbose_name = "Special Shop"
        verbose_name_plural = "Special Shops"
        ordering = ['order', 'id']

    @property
    def is_event(self):
        return self.start_time is not None or self.end_time is not None

    def is_open(self, now=None):
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'Must be after the start time.'})

    def __str__(self):
        return self.name


def open_special_shops(now=None):
    """Special shops a player can use right now."""
    now = now or timezone.now()
    return SpecialShop.objects.filter(is_active=True).filter(
        models.Q(start_time__isnull=True) | models.Q(start_time__lte=now),
        models.Q(end_time__isnull=True) | models.Q(end_time__gte=now),
    )


class SpecialShopItem(models.Model):
    """
    Special item
    """
    id = models.AutoField(primary_key=True)
    shop = models.ForeignKey('shops.SpecialShop', on_delete=models.CASCADE, related_name='items')

    item = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE, related_name='special_shop_items', help_text="Item endgame")
    exchange = models.ManyToManyField('items.ItemTemplate', through='shops.SpecialShopItemRecipe', related_name='+' )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Special Shop Item"
        verbose_name_plural = "Special Shop Items"
        ordering = ['shop', 'id']
    def __str__(self):
        return f"Special Item: {self.item.name}"

class SpecialShopItemRecipe(models.Model):
    """
    Model for special item recipe
    """
    recipe = models.ForeignKey('shops.SpecialShopItem', on_delete=models.CASCADE)
    item = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE, help_text="Item required for exchange")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Special Shop Item Recipe"
        verbose_name_plural = "Special Shop Item Recipes"
        ordering = ['recipe', 'item']
        unique_together = ('recipe', 'item')
    def __str__(self):
        return f"{self.quantity} x {self.item.name} for {self.recipe.item.name}"
    