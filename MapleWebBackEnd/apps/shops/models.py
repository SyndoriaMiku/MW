from datetime import timezone
from django.db import models
from django.forms import ValidationError

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
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey('shops.ShopCategory', on_delete=models.CASCADE, related_name='shop_items')
    item_template = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE)
    price = models.PositiveBigIntegerField(default=0)
    stock = models.PositiveIntegerField(default=0, help_text="0 means unlimited stock")
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

    