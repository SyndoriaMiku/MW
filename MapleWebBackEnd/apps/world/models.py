from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator



class ExperienceTable(models.Model):
    """
    Experience table for character leveling
    """
    level = models.IntegerField(unique=True)
    required_exp = models.IntegerField() #EXP needed to level up
    
    def __str__(self):
        return f"Level {self.level} need {self.required_exp} EXP"
    
class EnemyTemplate(models.Model):
    """
    Template for enemy types
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    level = models.IntegerField()
    is_boss = models.BooleanField(default=False) #True if boss, False if normal monster
    skills = models.ManyToManyField('skills.SkillTemplate', blank=True, related_name='enemies') #Skills that the enemy can use

    base_hp = models.IntegerField()
    base_mp = models.IntegerField()
    base_att = models.IntegerField()

    # Regular reward
    exp_reward = models.IntegerField() #EXP rewarded for defeating this enemy
    lumis_reward_min = models.IntegerField() #Lumis rewarded for defeating this enemy
    lumis_reward_max = models.IntegerField() #Lumis rewarded for defeating this enemy


class LootTable(models.Model):
    """
    Loot table for monsters
    """
    class DropType(models.TextChoices):
        COMMON = 'common', 'Easily dropped, gain a lot of drop increase'
        EPIC = 'epic', 'Hard to drop, can only boosted by specific consumable item and limited events'
        LEGENDARY = 'legendary', 'Very rare, cannot increase drop rate'

    enemy = models.ForeignKey('world.EnemyTemplate', on_delete=models.CASCADE, related_name='loot_tables')
    item_template = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE)

    base_drop_rate = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)]) #Base drop rate (0 to 1)
    min_quantity = models.IntegerField(default=1) #Minimum quantity dropped
    max_quantity = models.IntegerField(default=1) #Maximum quantity dropped

    drop_type = models.CharField(max_length=10, choices=DropType.choices, default=DropType.COMMON)

    class Meta:
        unique_together = ('enemy', 'item_template')
        verbose_name = "Loot Table"
        verbose_name_plural = "Loot Tables"
        ordering = ['enemy', 'item_template']

    def __str__(self):
        return f"{self.enemy.name} - {self.item_template.name}"

# ===================================================================
# SECTION: WORLD DUNGEON & MAP MODELS
# ===================================================================
class BaseStageTemplate(models.Model):
    """
    Base template for stages in dungeons
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Requirement
    required_level = models.IntegerField(default=1) #Minimum level to enter the dungeon
    # Content
    enemies = models.ManyToManyField('world.EnemyTemplate',through='world.StageEnemy', related_name='%(class)s_stages')
    # Reward
    exp_reward = models.IntegerField(default=0) #EXP rewarded for completing this stage
    lumis_reward = models.IntegerField(default=0) #Lumis rewarded for completing this

    class Meta:
        abstract = True
        ordering = ['required_level', 'id']

    def __str__(self):
        return self.name
    
class NormalDungeonTemplate(BaseStageTemplate):
    """
    Normal dungeon template
    """
    stamina_cost = models.PositiveIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)]) #Stamina cost to enter the dungeon
    

    class Meta(BaseStageTemplate.Meta):
        verbose_name = "Normal Dungeon Template"
        verbose_name_plural = "Normal Dungeon Templates"

class BossDungeonTemplate(BaseStageTemplate):
    """
    Boss dungeon template
    """
    class TimeType(models.TextChoices):
        DAILY = 'daily', 'Can be done once per day'
        WEEKLY = 'weekly', 'Can be done once per week'
        MONTHLY = 'monthly', 'Can be done once per month'

    max_party_size = models.IntegerField(default=4, validators=[MinValueValidator(1), MaxValueValidator(10)]) #Maximum party size
    time_type = models.CharField(max_length=10, choices=TimeType.choices,default=TimeType.DAILY) #How often the dungeon can be done


    class Meta(BaseStageTemplate.Meta):
        verbose_name = "Boss Dungeon Template"
        verbose_name_plural = "Boss Dungeon Templates"