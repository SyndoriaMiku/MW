from django.db import models

class QuestTemplate(models.Model):
    """
    Quest Template model to define quests in the game.
    """
    class QuestType(models.TextChoices):
        DAILY = 'daily', 'Daily Quest'
        WEEKLY = 'weekly', 'Weekly Quest'
        ONCE = 'once', 'One-time Quest'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    quest_type = models.CharField(max_length=10, choices=QuestType.choices, default=QuestType.ONCE)

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

    dungeon_to_clear = models.ForeignKey('world.NormalDungeonTemplate', null=True, blank=True, on_delete=models.CASCADE)
    clear_count = models.IntegerField(default=0)

    boss_dungeon_to_clear = models.ForeignKey('world.BossDungeonTemplate', null=True, blank=True, on_delete=models.CASCADE)
    boss_clear_count = models.IntegerField(default=0)

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


class CharacterQuest(models.Model):
    """Tracks a character's progress on a quest."""
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CLAIMED = 'claimed', 'Reward Claimed'

    character = models.ForeignKey('characters.Character', on_delete=models.CASCADE, related_name='quests')
    quest = models.ForeignKey('quests.QuestTemplate', on_delete=models.CASCADE, related_name='character_quests')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    from django.utils import timezone
    last_reset_at = models.DateTimeField(default=timezone.now, help_text="Used to track daily/weekly resets")

    class Meta:
        unique_together = ('character', 'quest')
        verbose_name = "Character Quest"
        verbose_name_plural = "Character Quests"
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.character.name} - {self.quest.name} ({self.status})"


class CharacterQuestObjective(models.Model):
    """Tracks progress on individual quest objectives."""
    character_quest = models.ForeignKey('quests.CharacterQuest', on_delete=models.CASCADE, related_name='objective_progress')
    objective = models.ForeignKey('quests.QuestObjective', on_delete=models.CASCADE)
    current_count = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('character_quest', 'objective')
        verbose_name = "Quest Objective Progress"
        verbose_name_plural = "Quest Objective Progress"
        ordering = ['character_quest', 'objective']

    def __str__(self):
        return f"{self.character_quest} - {self.objective} ({self.current_count})"