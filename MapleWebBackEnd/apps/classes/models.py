from django.db import models

from apps.items.models import WEAPON_TYPE_CHOICES

class CharacterClass(models.Model):
    """
    Character class model
    """
    name = models.CharField(max_length=50, unique=True)
    #Attack ratio
    class MainStat(models.TextChoices):
        STRENGTH = 'str', 'Strength'
        AGILITY = 'agi', 'Agility'
        INTELLIGENCE = 'int', 'Intelligence'
        ALL = 'all', 'All Stats'
    main_stat = models.CharField(max_length=3, choices=MainStat.choices, help_text="Main stat for the class")

    #Growth rate of stats
    hp_growth = models.FloatField(default=0)
    mp_growth = models.FloatField(default=0)
    str_growth = models.FloatField(default=0)
    agi_growth = models.FloatField(default=0)
    int_growth = models.FloatField(default=0)
    def __str__(self):
        return self.name
    
class Job(models.Model):
    """
    Job of class make u use different skills
    """
    
    name = models.CharField(max_length=50, unique=True) #Job name
    character_class = models.ForeignKey('classes.CharacterClass', on_delete=models.CASCADE) #Class that job belongs to
    main_stat_weight = models.FloatField(default=1.0, help_text="Weight for main stat in damage calculation")
    weapon_type = models.CharField(
        max_length=20, choices=WEAPON_TYPE_CHOICES, null=True, blank=True,
        help_text="The one weapon type this job can equip. Empty = any weapon (not configured yet).",
    )

    def __str__(self):
        return f"{self.name} with main stat {self.character_class.main_stat}"