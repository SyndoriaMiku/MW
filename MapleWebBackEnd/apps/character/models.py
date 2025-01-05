from django.db import models


#Create UUID
import uuid

def generate_hex_id():
    return uuid.uuid4().hex[:8] #Generate a 8-character hex id


# Create your models here.
class Character(models.Model):
    """
    Character model
    """
    id = models.CharField(
        max_length=8,
        primary_key=True,
        default=generate_hex_id,
        editable=False
    )
    name = models.CharField(max_length=20)
    
    #stats
    
    base_hp = models.IntegerField(default=50) #base stat
    base_mp = models.IntegerField(default=5) #base stat
    base_att = models.IntegerField(default=5) #base stat
    base_strength = models.IntegerField(default=10) #base stat
    base_agility = models.IntegerField(default=10) #base stat
    base_intelligence = models.IntegerField(default=10) #base stat
    
    #multipliers
    hp_multiplier = models.FloatField(default=1.0) #100% base hp
    mp_multiplier = models.FloatField(default=1.0) #100% base mp
    att_multiplier = models.FloatField(default=1.0) #100% base att
    strength_multiplier = models.FloatField(default=1.0) #100% base strength
    agility_multiplier = models.FloatField(default=1.0) #100% base agility
    intelligence_multiplier = models.FloatField(default=1.0) #100% base intelligence
    
    #fixed stats
    fixed_hp = models.IntegerField(default=0) #Fixed hp
    fixed_mp = models.IntegerField(default=0) #Fixed mp
    fixed_att = models.IntegerField(default=0) #Fixed att
    fixed_strength = models.IntegerField(default=0) #Fixed strength
    fixed_agility = models.IntegerField(default=0) #Fixed agility
    fixed_intelligence = models.IntegerField(default=0) #Fixed intelligence
      
    #drop rate
    drop_rate = models.FloatField(default=1) #100% base drop rate
    
    #information
    character_class = models.ForeignKey('CharacterClass', on_delete=models.SET_NULL, null=True)
    Job = models.ForeignKey('Job', on_delete=models.SET_NULL, null=True)
    
    #leveling
    level = models.IntegerField(default=1)
    current_exp = models.IntegerField(default=0)
    
    
    
    def __str__(self):
        return self.id
    
    #logic
    
    def calculate_stat(self, base, multiplier, fixed):
        return int((base * multiplier) + fixed)
    
    def get_stats(self):
        return {
            "hp": self.calculate_stat(self.base_hp, self.hp_multiplier, self.fixed_hp),
            "mp": self.calculate_stat(self.base_mp, self.mp_multiplier, self.fixed_mp),
            "att": self.calculate_stat(self.base_att, self.att_multiplier, self.fixed_att),
            "strength": self.calculate_stat(self.base_strength, self.strength_multiplier, self.fixed_strength),
            "agility": self.calculate_stat(self.base_agility, self.agility_multiplier, self.fixed_agility),
            "intelligence": self.calculate_stat(self.base_intelligence, self.intelligence_multiplier, self.fixed_intelligence),
            "drop_rate": self.drop_rate
        }
    
    def calculate_attack_power(self):
        if self.character_class:
            #Calculate attack power based on stats
            strength_att = self.strength / self.character_class.strength_ratio
            agility_att = self.agility / self.character_class.agility_ratio
            intelligence_att = self.intelligence / self.character_class.intelligence_ratio
            
            #Calculate attack power
            return int(self.att + strength_att + agility_att + intelligence_att)
        return self.att
    
    def gain_exp(self, exp):
        """
        Gain experience points, then check if the character can level up
        """
        self.current_exp += exp
        current_level = Level.objects.get(level=self.level)
        next_level = Level.objects.filter(level=self.level + 1).first()
        
        #check max level
        if not next_level or current_level.required_exp==0:
            return #do not get exp if max level
        
        #gain exp
        self.current_exp += exp
        while self.current_exp >= next_level.required_exp:
            self.level_up(next_level)
            next_level = Level.objects.filter(level=self.level + 1).first()
        
            
    def level_up(self, next_level):
        """
        Level up the character and reset the experience points
        """
        next_level = Level.objects.filter(level=self.level + 1).first()
        
        #Check next level
        if next_level and next_level.required_exp > 0:
            self.level += 1
            self.current_exp -= next_level.required_exp
            #Increase stats
            #Increase stats
            self.hp += self.character_class.hp_growth
            self.mp += self.character_class.mp_growth
            self.strength += self.character_class.strength_growth
            self.agility += self.character_class.agility_growth
            self.intelligence += self.character_class.intelligence_growth
        else:
            self.current_exp = 0
            
        

        
    
    
class CharacterClass(models.Model):
    name = models.CharField(max_length=50, unique=True)
    #Attack ratio
    strength_ratio = models.FloatField(default=0) #Stat need to increase 1 attack
    agility_ratio = models.FloatField(default=0) #Stat need to increase 1 agility
    intelligence_ratio = models.FloatField(default=0) #Stat need to increase 1 intelligence
    
    #Growth rate of stats
    hp_growth = models.FloatField(default=0)
    mp_growth = models.FloatField(default=0)
    strength_growth = models.FloatField(default=0)
    agility_growth = models.FloatField(default=0)
    intelligence_growth = models.FloatField(default=0)
    def __str__(self):
        return self.name
    
class Job(models.Model):
    """
    Job of class make u use different skills
    """
    
    name = models.CharField(max_length=50, unique=True) #Job name
    character_class = models.ForeignKey(CharacterClass, on_delete=models.CASCADE) #Class that job belongs to
    
    def __str__(self):
        return self.name
    


class Level(models.Model):
    """
    Level model
    """ 
    level = models.IntegerField(unique=True)
    required_exp = models.IntegerField() #EXP needed to level up
    
    def __str__(self):
        return f"Level {self.level} need {self.required_exp} EXP"
    
class Equipped(models.Model):
    character = models.OneToOneField(
        Character,
        on_delete=models.CASCADE,
        related_name='equipped'
    )
    
    ring1 = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='ring1_equipped')
    ring2 = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='ring2_equipped')
    ring3 = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='ring3_equipped')
    ring4 = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='ring4_equipped')
    pendant = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='pendant_equipped')
    earring = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='earring_equipped')
    belt = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='belt_equipped')
    hat = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='hat_equipped')
    top = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='top_equipped')
    bottom = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='bottom_equipped')
    shoes = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='shoes_equipped')
    cape = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='cape_equipped')
    gloves = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='gloves_equipped')
    shoulder = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='shoulder_equipped')
    face = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='face_equipped')
    eye = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='eye_equipped')
    weapon = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='weapon_equipped')
    
    def __str__(self):
        return f"{self.character.name}'s Equipped"    


    
        
