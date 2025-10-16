from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


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
    # Item template
    name = models.CharField(max_length=100)
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES) #Item type
    weapon_type = models.CharField(max_length=20, choices=WEAPON_TYPE_CHOICES, blank=True, null=True) #Weapon type (only for weapons)
    minimum_level = models.IntegerField(default=1) #Minimum level to equip the item
    class_restriction = models.ManyToManyField('classes.CharacterClass', blank=True) #Class restriction (empty means no restriction)
    job_restriction = models.ManyToManyField('classes.Job', blank=True) #Job restriction (empty means no restriction)
    is_tradeable = models.BooleanField(default=True) #If the item can be traded
    is_sellable = models.BooleanField(default=True) #If the item can be sold to NPC
    # Upgrade information
    lumen_tier = models.ForeignKey('items.LumenTierProperty', on_delete=models.SET_NULL, null=True, blank=True, help_text="Lumen Tier for this item (if upgradable)")
    aurora_tier = models.ForeignKey('items.AuroraProperty', on_delete=models.SET_NULL, null=True, blank=True, help_text="Aurora Tier for this item (if upgradable)")
    # Stats boost based
    hp_boost = models.IntegerField(default=0)
    mp_boost = models.IntegerField(default=0)
    att_boost = models.IntegerField(default=0)
    str_boost = models.IntegerField(default=0)
    agi_boost = models.IntegerField(default=0)
    int_boost = models.IntegerField(default=0)
    all_stats_boost = models.IntegerField(default=0)
    drop_rate_boost = models.FloatField(default=0)

    # Description
    description = models.TextField(blank=True)

    # Sell price
    sell_price = models.IntegerField(default=1)

    @property
    def is_stackable(self):
        return self.item_type in ['use', 'etc']
    
    
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
    str_boost = models.IntegerField(default=0)
    agi_boost = models.IntegerField(default=0)
    int_boost = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.item_set.name} {self.required_count} Set Items Effect"
    
# ===================================================================
# SECTION: PROPERTY & RULE MODELS
# ===================================================================
class LumenTierProperty(models.Model):
    """
    Properties for each Lumen Tier
    """
    name = models.CharField(max_length=255, unique=True)
    tier = models.IntegerField()
    max_lumen_level = models.IntegerField(default=0, help_text="Maximum Lumen Ascend Level for this tier")
    heavy_failure_level = models.IntegerField(default=0, help_text="Level to drop to on heavy failure") 
    class Meta:
        verbose_name = "Lumen Tier Property"
        verbose_name_plural = "Lumen Tier Properties"
        ordering = ['tier']
    def __str__(self):
        return f"Tier {self.tier} - {self.name} (Max Level {self.max_lumen_level})"
    
class AuroraProperty(models.Model):
    """
    Properties for each Aurora
    """
    name = models.CharField(max_length=255, unique=True)
    tier = models.IntegerField(default=0)
    max_aurora_level = models.IntegerField(default=0, help_text="Maximum Aurora Level for this property")

    class Meta:
        verbose_name = "Aurora Property"
        verbose_name_plural = "Aurora Properties"
        ordering = ['tier']
    def __str__(self):
        return f"Tier {self.tier} - {self.name} (Max Level {self.max_aurora_level})"   
     
class LumenCostRule(models.Model):
    """
    Cost and success rules for Lumen Ascend
    """
    lumen_tier = models.ForeignKey('items.LumenTierProperty', on_delete=models.CASCADE, related_name='cost_rules')
    # Current level
    current_level = models.IntegerField(default=0, help_text="Current Lumen Ascend Level before attempting")
    lumis_cost = models.BigIntegerField(default=0, help_text="Cost in Lumis to attempt ascend")
    success_rate = models.FloatField(default=1.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], help_text="Success rate, item level increase")
    failure_rate = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], help_text="Failure rate, item do not change")
    heavy_failure_rate = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], help_text="Heavy failure rate, item lost level to certain point")

    def clean(self):
        if self.success_rate + self.failure_rate + self.heavy_failure_rate != 1.0:
            raise ValidationError("The sum of success, failure, and heavy failure rates must equal 1.")

    class Meta:
        verbose_name = "Lumen Cost Rule"
        verbose_name_plural = "Lumen Cost Rules"
        ordering = ['lumen_tier', 'current_level']
    def __str__(self):
        return (
            f"Lumen Tier {self.lumen_tier.tier} - Level {self.current_level}: "
            f"Cost {self.lumis_cost} Lumis, Success {self.success_rate}%, "
            f"Failure {self.failure_rate}%, Heavy Failure {self.heavy_failure_rate}%"
        )
# ===================================================================
# SECTION: STAT RULE MODELS
# ===================================================================

class AuroraLinePool(models.Model):
    """
    Pool of Aurora Lines
    """
    aurora_property = models.ForeignKey('items.AuroraProperty', on_delete=models.CASCADE, related_name='line_pools')
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, help_text="Item type")
    aurora_level = models.IntegerField(help_text="Aurora Level")
    stat_type = models.CharField(max_length=20, choices=STATS_CHOICES, help_text="Type of the line that stat boost")
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES, help_text="Type of the line")
    value = models.FloatField(help_text="Value of the line")
    weight = models.IntegerField(default=1, help_text="Relative weight for random selection")

    class Meta:
        verbose_name = "Aurora Line Pool"
        verbose_name_plural = "Aurora Line Pools"
        ordering = ['aurora_property', 'item_type', 'aurora_level', 'stat_type', 'line_type', 'value']
    
    def __str__(self):
        return (
            f"{self.item_type} (Level {self.min_level}+): "
            f"{self.stat_type} {self.value} ({self.line_type})"
        )

class LumenAscendRule(models.Model):
    """
    Stat boost rules for Lumen Ascend
    """
    lumen_tier = models.ForeignKey('items.LumenTierProperty', on_delete=models.CASCADE, related_name='ascend_rules')
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, help_text="Item type applicable for this rule")
    #Stat gain on this level up, e.g at level 1 gain 5hp, so lumen_level 1 hp_boost 5
    lumen_level = models.PositiveIntegerField(help_text="Lumen Ascend Level")

    #Stat gain
    hp_boost = models.IntegerField(default=0)
    mp_boost = models.IntegerField(default=0)
    att_boost = models.IntegerField(default=0)
    str_boost = models.IntegerField(default=0)
    agi_boost = models.IntegerField(default=0)
    int_boost = models.IntegerField(default=0)

    class Meta:
        unique_together = ('lumen_tier', 'item_type', 'lumen_level')
        verbose_name = "Lumen Ascend Stat Rule"
        verbose_name_plural = "Lumen Ascend Stat Rules"
        ordering = ['lumen_tier', 'item_type', 'lumen_level']
    def __str__(self):
        return (
            f"Lumen Tier {self.lumen_tier.tier} - {self.item_type} - Level {self.lumen_level}"
        )

