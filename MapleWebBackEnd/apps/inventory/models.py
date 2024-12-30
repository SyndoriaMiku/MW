from django.db import models

# Create your models here.
class Item(models.Model):
    Type_Choices = [
        ('pendant', 'Pendant'),
        ('earring', 'Earring'),
        ('belt', 'Belt'),
        ('hat', 'Hat'),
        ('top', 'Top'),
        ('bottom', 'Bottom'),
        ('shoes', 'Shoes'),
        ('cape', 'Cape'),
        ('gloves', 'Gloves'),
        ('shoulder', 'Shoulder Armor'),
        ('face', 'Face Accessory'),
        ('eye', 'Eye Accessory'),
        ('weapon', 'Weapon'),
        ('use', 'Consumable'),
        ('etc', 'Etc')
    ]
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=Type_Choices) #Item type
    hp_boost = models.IntegerField(default=0)
    mp_boost = models.IntegerField(default=0)
    att_boost = models.IntegerField(default=0)
    strength_boost = models.IntegerField(default=0)
    agility_boost = models.IntegerField(default=0)
    intelligence_boost = models.IntegerField(default=0)
    all_stats_boost = models.IntegerField(default=0)
    drop_rate_boost = models.FloatField(default=0)
    description = models.TextField(blank=True)
    
    #Sell price
    sell_price = models.IntegerField(default=1) 
    
    #Lumen Ascension
    lumen_asc_level = models.IntegerField(default=0)
    
    #Aurora Level
    aurora_level = models.IntegerField(default=0)
    
    
    def __str__(self):
        return self.name
    
    
class ItemSet(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    items = models.ManyToManyField(Item, blank=True, related_name='item_sets')
    
    def __str__(self):
        return self.name
    
class ItemSetEffect(models.Model):
    item_set = models.ForeignKey(ItemSet, on_delete=models.CASCADE, related_name='effects')
    
    
class Inventory(models.Model):
    character = models.OneToOneField(
        character.Character,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    items = models.ManyToManyField(Item, blank=True) #Items in the inventory
    
    def __str__(self):
        return f"{self.character.name}'s Inventory"