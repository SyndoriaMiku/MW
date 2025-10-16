from django.db import models

class CharacterClass(models.Model):
    """
    Character class model
    """
    name = models.CharField(max_length=50, unique=True)
    #Attack ratio
    str_ratio = models.FloatField(default=0) #Stat need to increase 1 attack
    agi_ratio = models.FloatField(default=0) #Stat need to increase 1 agility
    int_ratio = models.FloatField(default=0) #Stat need to increase 1 intelligence
    
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
    
    def __str__(self):
        return self.name