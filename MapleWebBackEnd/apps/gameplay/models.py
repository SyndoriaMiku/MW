from django.db import models

# Create your models here.

class Skill(models.Model):
    """
    Skill of job
    """
    name = models.CharField(max_length=50) #Skill name
    job = models.ForeignKey("character.Job", on_delete=models.CASCADE) #Job that skill belongs to
    mp_cost = models.IntegerField(default=0) #MP cost of the skill
    cooldown = models.IntegerField(default=0) #Cooldown of the skill
    description = models.TextField(blank=True) #Description of the skill
    
    def __str__(self):
        return self.name
    
class Monster(models.Model):
    """
    Monster model
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    hp = models.IntegerField(default=50)
    mp = models.IntegerField(default=5)
    att = models.IntegerField(default=5)

    def __str__(self):
        return self.name
        
class Drop(models.Model):
    NORMAL = 'normal'
    EPIC = 'epic'
    
    DROP_TYPE_CHOICE = [
        (NORMAL, 'Normal Drop'),
        (EPIC, 'Epic Drop')
    ]
    
    monster = models.ForeignKey(
        Monster,
        on_delete=models.CASCADE,
        related_name='drops'
    )
    item = models.ForeignKey(
        "inventory.Item",
        on_delete=models.CASCADE,
        related_name='drops'
    )
    drop_rate = models.FloatField() #0.1 = 10% drop rate
    quantity_min = models.IntegerField() #Minimum quantity of the item dropped
    quantity_max = models.IntegerField() #Maximum quantity of the item dropped
    drop_type = models.CharField(
        max_length=10,
        choices=DROP_TYPE_CHOICE,
        default=NORMAL
    )
    
    def __str__(self):
        return f"{self.item.name} from {self.monster.name}"   
    
    def calculate_drop(self, player_drop_rate):
        #Calculate the drop quantity
        import random
        
        if self.drop_type == Drop.NORMAL:
            final_drop_rate = self.item.drop_rate * player_drop_rate
            if random.random() <= final_drop_rate:
                quantity = random.randint(self.quantity_min, self.quantity_max)
                return {"item": self.item.name, "quantity": quantity}
        elif self.drop_type == Drop.EPIC:
            if random.random() <= self.item.drop_rate:
                quantity = random.randint(self.quantity_min, self.quantity_max)
                return {"item": self.item.name, "quantity": quantity}
        return None