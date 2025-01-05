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
    minimum_level = models.IntegerField(default=1) #Minimum level to equip the item
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
    required_count = models.IntegerField() #Number of items required to activate the effect
    hp_boost = models.IntegerField(default=0)
    mp_boost = models.IntegerField(default=0)
    att_boost = models.IntegerField(default=0)
    strength_boost = models.IntegerField(default=0)
    agility_boost = models.IntegerField(default=0)
    intelligence_boost = models.IntegerField(default=0)
    all_stats_boost = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.item_set.name} {self.required_count} Set Items Effect"
    
class Inventory(models.Model):
    character = models.OneToOneField(
        "character.Character",
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    items = models.ManyToManyField(Item, blank=True) #Items in the inventory
    
    def __str__(self):
        return f"{self.character.name}'s Inventory"
    
 
class AuroraLine(models.Model):
    """
    Aurora Line for an item
    """
    Stats_Choices = [
        ('hp', 'HP'),
        ('mp', 'MP'),
        ('att', 'Attack'),
        ('str', 'Strength'),
        ('agi', 'Agility'),
        ('int', 'Intelligence'),
        ('all', 'All Stats'),
        ('drop', 'Drop Rate')
    ]
    
    Line_Type_Choices = [
        ('flat', 'Flat'),
        ('percent', 'Percent')
    ]
    
    Item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='aurora_lines')
    
    stat_type = models.CharField(max_length=20, choices=Stats_Choices)
    line_type = models.CharField(max_length=20, choices=Line_Type_Choices)
    value = models.FloatField() #Value of the line
    
    def __str__(self):
        return f"{self.stat_type} {self.value} {self.line_type}"
    
    def apply_lines(character, item):
        #Apply the lines to the character
        
        for line in item.aurora_lines.all():
            if line.line_type == 'flat':
                if line.stat.type == 'all':
                    for stat in ['str', 'agi', 'int']:
                        setattr (character, f"fixed_{stat}", getattr(character, f"fixed_{stat}") + line.value)
                else:
                    setattr(character, f"fixed_{line.stat_type}", getattr(character, f"fixed_{line.stat_type}") + line.value)
            elif line.line_type == 'percent':
                if line.stat_type == 'all':
                    for stat in ['str', 'agi', 'int']:
                        multiplier_field = f"{stat}_multiplier"
                        setattr(character, multiplier_field, getattr(character, multiplier_field) + line.value / 100)
                    else:
                        multiplier_field = f"{line.stat_type}_multiplier"
                        setattr(character, multiplier_field, getattr(character, multiplier_field) + line.value / 100)
                                         

class AuroraLinePool(models.Model):
    """
    Pool of Aurora Lines
    """
    item_type = models.CharField(max_length=20, choices=Item.Type_Choices, help_text="Item type")
    aurora_level = models.IntegerField(help_text="Aurora Level")
    min_level = models.IntegerField(help_text="Minimum level of the item")
    stat_type = models.CharField(max_length=20, choices=AuroraLine.Stats_Choices, help_text="Type of the line that stat boost")
    line_type = models.CharField(max_length=20, choices=AuroraLine.Line_Type_Choices, help_text="Type of the line")
    value = models.FloatField(help_text="Value of the line")
    
    def __str__(self):
        return (
            f"{self.item_type} (Level {self.min_level}+): "
            f"{self.stat_type} {self.value} ({self.line_type})"
        )
        

    
    