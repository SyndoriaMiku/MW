from django.db import models

class Skill(models.Model):
    """
    Skill of job
    """
    name = models.CharField(max_length=50) #Skill name
    job = models.ForeignKey("classes.CharacterJob", on_delete=models.CASCADE) #Job that skill belongs to
    mp_cost = models.IntegerField(default=0) #MP cost of the skill
    cooldown = models.IntegerField(default=0) #Cooldown of the skill
    description = models.TextField(blank=True) #Description of the skill
    
    def __str__(self):
        return self.name