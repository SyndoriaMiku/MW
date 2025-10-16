from django.db import models

class QuestTemplate(models.Model):
    """
    Quest Template model to define quests in the game.
    """
    class QuestType(models.TextChoices):
        MAIN = 'main', 'Main Quest'
        SIDE = 'side', 'Side Quest'
        DAILY = 'daily', 'Daily Quest'
        WEEKLY = 'weekly', 'Weekly Quest'
        EVENT = 'event', 'Event Quest'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    quest_type = models.CharField(max_length=10, choices=QuestType.choices, default=QuestType.SIDE)

    #Requirements to start the quest
    required_level = models.IntegerField(default=1)
    prerequisite_quests = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='unlocks_quests')

    # EXP and Lumis rewarded for completing the quest
    exp_reward = models.IntegerField(default=0)
    lumis_reward = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Quest Template"
        verbose_name_plural = "Quest Templates"
        ordering = ['id']

class QuestObjective(models.Model):
    """
    Objectives for a quest.
    """
    quest = models.ForeignKey('quests.QuestTemplate', on_delete=models.CASCADE, related_name='objectives')
    
    enemy_to_defeat = models.ForeignKey('world.EnemyTemplate', null=True, blank=True, on_delete=models.CASCADE)
    defeat_count = models.IntegerField(default=0)

    item_to_collect = models.ForeignKey('items.ItemTemplate', null=True, blank=True, on_delete=models.CASCADE)
    collect_count = models.IntegerField(default=0)

    dungeon_to_clear = models.ForeignKey('world.DungeonTemplate', null=True, blank=True, on_delete=models.CASCADE)
    clear_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Objective for {self.quest.name}"
    
class QuestReward(models.Model):
    """
    Rewards for completing a quest.
    """
    quest = models.ForeignKey('quests.QuestTemplate', on_delete=models.CASCADE, related_name='rewards')
    item_template = models.ForeignKey('items.ItemTemplate', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    class Meta:
        verbose_name = "Quest Reward"
        verbose_name_plural = "Quest Rewards"
        ordering = ['quest', 'item_template']

    def __str__(self):
        return f"Reward for {self.quest.name}"