from django.db import models
from apps.items.models import STATS_CHOICES, LINE_TYPE_CHOICES

class InventoryItem(models.Model):
    """
    Item in inventory of a character
    """
    template = models.ForeignKey('items.ItemTemplate', verbose_name=("Item Template"), on_delete=models.CASCADE)
    owner = models.ForeignKey('characters.Character', verbose_name=("Owner"), on_delete=models.CASCADE, related_name='inventory_items')

    lumen_ascend_level = models.IntegerField(default=0) #Level of lumen ascend
    aurora_level = models.IntegerField(default=0) #Level of aurora

    quantity = models.IntegerField(default=1) #Quantity of the item (for stackable items)

    is_untrade = models.BooleanField(default=False) #Some item cannot trade if eqquipped or expired
    expired_at = models.DateTimeField(null=True, blank=True) #Expiration date of the item, null if not expiring
    is_destroyed = models.BooleanField(default=False, help_text="Item is destroyed (fragment) and cannot be equipped until restored")

    def __str__(self):
        return self.template.name

class SoldItem(models.Model):
    """
    A snapshot of an item sold to the NPC, kept so the player can buy it back
    at the price it sold for. Only the latest BUYBACK_LIMIT sales per character
    are kept.
    """
    BUYBACK_LIMIT = 10

    owner = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='sold_items')
    template = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.PositiveIntegerField(help_text="Lumis paid for the sale, and charged to buy it back")
    lumen_ascend_level = models.IntegerField(default=0)
    aurora_level = models.IntegerField(default=0)
    aurora_lines = models.JSONField(default=list, blank=True, help_text="[{line_index, stat_type, line_type, value}]")
    is_untrade = models.BooleanField(default=False)
    expired_at = models.DateTimeField(null=True, blank=True)
    sold_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sold_at', '-id']

    def __str__(self):
        return f"{self.quantity}x {self.template.name} sold by {self.owner}"


class AuroraLine(models.Model):
    """
    Aurora Line for an item
    """
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='aurora_lines')
    line_index = models.IntegerField(default=0, help_text="Index of the line (0, 1, 2) to distinguish lines")
    stat_type = models.CharField(max_length=20, choices=STATS_CHOICES)
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES)
    value = models.FloatField() #Value of the line

    def __str__(self):
        return f"{self.stat_type} {self.value} {self.line_type}"


class PendingAuroraRoll(models.Model):
    """
    Stores temporarily rolled Aurora Lines for items like Choice Cubes
    until the user confirms which ones to keep.
    """
    inventory_item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name='pending_aurora_roll')
    modifier_type = models.CharField(max_length=50, help_text="The type of modifier used (e.g. REROLL_CHOICE, REROLL_TRIPLE_CHOICE)")
    generated_lines_data = models.JSONField(default=list, help_text="JSON storing the newly rolled lines data")
    new_aurora_level = models.IntegerField(
        null=True, blank=True,
        help_text="Aurora level of the rolled lines (a tier-up). Applied only if the new lines are taken.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def raises_level(self):
        """A tier-up: the rolled lines come with a higher Aurora level, so they must be taken."""
        return self.new_aurora_level is not None and self.new_aurora_level > self.inventory_item.aurora_level

    class Meta:
        verbose_name = "Pending Aurora Roll"
        verbose_name_plural = "Pending Aurora Rolls"

    def __str__(self):
        return f"Pending roll for {self.inventory_item}"
