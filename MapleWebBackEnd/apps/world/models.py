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
    skills = models.ManyToManyField('skilles.SkillTemplate', through='EnemySkill', blank=True, related_name='enemies') #Skills that the enemy can use

    base_hp = models.IntegerField()
    base_mp = models.IntegerField()
    base_att = models.IntegerField()

    # Regular reward
    exp_reward = models.IntegerField() #EXP rewarded for defeating this enemy
    lumis_reward_min = models.IntegerField() #Lumis rewarded for defeating this enemy
    lumis_reward_max = models.IntegerField() #Lumis rewarded for defeating this enemy

class EnemySkill(models.Model):
    """
    Skill mapping for an enemy, defining initial cooldown and priority.
    """
    enemy_template = models.ForeignKey(EnemyTemplate, on_delete=models.CASCADE, related_name='enemy_skills')
    skill_template = models.ForeignKey('skilles.SkillTemplate', on_delete=models.CASCADE)
    initial_cd = models.IntegerField(default=0, help_text="Initial turns to wait before first use")
    priority_index = models.IntegerField(default=1, help_text="Higher number means higher priority. Must be unique per enemy.")

    class Meta:
        unique_together = (('enemy_template', 'priority_index'), ('enemy_template', 'skill_template'))
        verbose_name = "Enemy Skill"
        verbose_name_plural = "Enemy Skills"
        ordering = ['-priority_index']

    def __str__(self):
        return f"{self.enemy_template.name} - {self.skill_template.name} (Priority {self.priority_index})"

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
    is_party_shared = models.BooleanField(default=False, help_text="If True, this item drops for the whole party pool, and the Party Leader distributes it.")

    class Meta:
        unique_together = ('enemy', 'item_template', 'is_party_shared')
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
    
    enemies = models.ManyToManyField('world.EnemyTemplate', through='NormalStageEnemy', related_name='normal_stages', blank=True)

    class Meta(BaseStageTemplate.Meta):
        verbose_name = "Normal Dungeon Template"
        verbose_name_plural = "Normal Dungeon Templates"

class NormalStageEnemy(models.Model):
    stage = models.ForeignKey(NormalDungeonTemplate, on_delete=models.CASCADE, related_name='stage_enemies')
    enemy = models.ForeignKey('world.EnemyTemplate', on_delete=models.CASCADE, related_name='normal_stage_appearances')
    count = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(6)], help_text="Number of enemies of this type. Max 6.")

    class Meta:
        unique_together = ('stage', 'enemy')
        verbose_name = "Normal Stage Enemy"
        verbose_name_plural = "Normal Stage Enemies"

    def __str__(self):
        return f"{self.count}x {self.enemy.name} in {self.stage.name}"

class BossDungeonTemplate(BaseStageTemplate):
    """
    Boss dungeon template
    """
    class TimeType(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    time_type = models.CharField(max_length=10, choices=TimeType.choices, default=TimeType.DAILY)
    max_party_size = models.IntegerField(default=4)
    
    enemies = models.ManyToManyField('world.EnemyTemplate', through='BossStageEnemy', related_name='boss_stages', blank=True)

    class Meta(BaseStageTemplate.Meta):
        verbose_name = "Boss Dungeon Template"
        verbose_name_plural = "Boss Dungeon Templates"

class BossStageEnemy(models.Model):
    stage = models.ForeignKey(BossDungeonTemplate, on_delete=models.CASCADE, related_name='stage_enemies')
    enemy = models.ForeignKey('world.EnemyTemplate', on_delete=models.CASCADE, related_name='boss_stage_appearances')
    count = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(6)], help_text="Number of enemies of this type. Max 6.")

    class Meta:
        unique_together = ('stage', 'enemy')
        verbose_name = "Boss Stage Enemy"
        verbose_name_plural = "Boss Stage Enemies"

    def __str__(self):
        return f"{self.count}x {self.enemy.name} in {self.stage.name}"


# ===================================================================
# SECTION: WORLD MAP MODELS
# ===================================================================

class Region(models.Model):
    """Represents a large area in the game world (e.g., Henesys, Perion)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    required_level = models.IntegerField(default=1)
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    class Meta:
        verbose_name = "Region"
        verbose_name_plural = "Regions"
        ordering = ['order']

    def __str__(self):
        return self.name


class Location(models.Model):
    """A specific location within a region (e.g., Henesys Hunting Ground 1)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    region = models.ForeignKey('world.Region', on_delete=models.CASCADE, related_name='locations')
    required_level = models.IntegerField(default=1)

    # Link to dungeon templates (if this location is a dungeon entrance)
    normal_dungeon = models.ForeignKey('world.NormalDungeonTemplate', on_delete=models.SET_NULL, null=True, blank=True, related_name='locations', help_text="Linked normal dungeon, if any")
    boss_dungeon = models.ForeignKey('world.BossDungeonTemplate', on_delete=models.SET_NULL, null=True, blank=True, related_name='locations', help_text="Linked boss dungeon, if any")

    # Field enemies for open-world hunting at this location
    field_enemies = models.ManyToManyField('world.EnemyTemplate', blank=True, related_name='field_locations', help_text="Enemies that can be encountered in the field")

    has_shop = models.BooleanField(default=False, help_text="Whether this location has an NPC shop")
    order = models.PositiveIntegerField(default=0, help_text="Display order within region")

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ['region', 'order']

    def __str__(self):
        return f"{self.region.name} - {self.name}"


class DungeonClearLog(models.Model):
    """Tracks dungeon clear records for cooldown enforcement (daily/weekly/monthly boss)."""
    character = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='dungeon_clears')
    dungeon = models.ForeignKey('world.BossDungeonTemplate', on_delete=models.CASCADE, related_name='clear_logs')
    cleared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dungeon Clear Log"
        verbose_name_plural = "Dungeon Clear Logs"
        ordering = ['-cleared_at']

    def __str__(self):
        return f"{self.character.name} cleared {self.dungeon.name} at {self.cleared_at}"