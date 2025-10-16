from django.db import models

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
    
    att_weight = models.FloatField(default=1.0, help_text="Damage gain each att point")
    main_stat_weight = models.FloatField(default=1.0, help_text="Damage gain each main stat point")
    secondary_stat_weight = models.FloatField(default=0.5, help_text="Damage gain each secondary stat point")

    def __str__(self):
        return f"{self.name} with main stat {self.character_class.main_stat}"