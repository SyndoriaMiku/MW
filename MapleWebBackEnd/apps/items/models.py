from django.db import models
TYPE_CHOICES = [
    ('pendant', 'Pendant'),
    ('earring', 'Earring'),
    ('ring', 'Ring'),
    ('belt', 'Belt'),
    ('face', 'Face Accessory'),
    ('eye', 'Eye Accessory'),
    ('hat', 'Hat'),
    ('top', 'Top'),
    ('bottom', 'Bottom'),
    ('shoes', 'Shoes'),
    ('cape', 'Cape'),
    ('gloves', 'Gloves'),
    ('shoulder', 'Shoulder Armor'),
    ('weapon', 'Weapon'),
    ('use', 'Consumable'),
    ('etc', 'Etc')
]

WEAPON_TYPE_CHOICES = [
    ('1hs', 'One Handed Sword'),
    ('2hs', 'Two Handed Sword'),
    ('1ha', 'One Handed Axe'),
    ('bow', 'Bow'),
    ('staff', 'Staff'),
    ('wand', 'Wand'),
    ('spear', 'Spear'),
]

STATS_CHOICES = [
    ('hp', 'HP'),
    ('mp', 'MP'),
    ('att', 'Attack'),
    ('str', 'Strength'),
    ('agi', 'Agility'),
    ('int', 'Intelligence'),
    ('all', 'All Stats'),
    ('drop', 'Drop Rate')
    ]

LINE_TYPE_CHOICES = [
        ('flat', 'Flat'),
        ('percent', 'Percent')
    ]


class ItemTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES) #Item type
    weapon_type = models.CharField(max_length=20, choices=WEAPON_TYPE_CHOICES, blank=True, null=True) #Weapon type (only for weapons)
    minimum_level = models.IntegerField(default=1) #Minimum level to equip the item
    class_restriction = models.ManyToManyField('classes.CharacterClass', blank=True) #Class restriction (empty means no restriction)
    job_restriction = models.ManyToManyField('classes.Job', blank=True) #Job restriction (empty means no restriction)
    #Stats boost based
    hp_boost = models.IntegerField(default=0)
    mp_boost = models.IntegerField(default=0)
    att_boost = models.IntegerField(default=0)
    str_boost = models.IntegerField(default=0)
    agi_boost = models.IntegerField(default=0)
    int_boost = models.IntegerField(default=0)
    all_stats_boost = models.IntegerField(default=0)
    drop_rate_boost = models.FloatField(default=0)
    description = models.TextField(blank=True)
    
    #Sell price
    sell_price = models.IntegerField(default=1) 

    @property
    def is_stackable(self):
        return self.type in ['use', 'etc']
    
    
    def __str__(self):
        return self.name
    
    
class ItemSet(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    items = models.ManyToManyField('items.ItemTemplate', blank=True, related_name='item_sets')
    
    def __str__(self):
        return self.name
    
class ItemSetEffect(models.Model):
    item_set = models.ForeignKey('items.ItemSet', on_delete=models.CASCADE, related_name='effects')
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
    
class AuroraLinePool(models.Model):
    """
    Pool of Aurora Lines
    """


    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, help_text="Item type")
    aurora_level = models.IntegerField(help_text="Aurora Level")
    min_level = models.IntegerField(help_text="Minimum level of the item")
    stat_type = models.CharField(max_length=20, choices=STATS_CHOICES, help_text="Type of the line that stat boost")
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES, help_text="Type of the line")
    value = models.FloatField(help_text="Value of the line")
    
    def __str__(self):
        return (
            f"{self.item_type} (Level {self.min_level}+): "
            f"{self.stat_type} {self.value} ({self.line_type})"
        )    