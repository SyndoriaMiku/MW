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
 
class AuroraLine(models.Model):
    """
    Aurora Line for an item
    """
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='aurora_lines')
    stat_type = models.CharField(max_length=20, choices=STATS_CHOICES)
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES)
    value = models.FloatField() #Value of the line
    
    def __str__(self):
        return f"{self.stat_type} {self.value} {self.line_type}"
    
    