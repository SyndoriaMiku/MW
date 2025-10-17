from django.db import models

class SkillTemplate(models.Model):
    """
    Template for all skills in the game.
    """
    class TargetType(models.TextChoices):
        SELF = 'SELF', 'Self'
        ALLY = 'ALLY', 'Single Ally'
        ENEMY = 'ENEMY', 'Single Enemy'
        E_AREA = 'E_AREA', 'Enemy Area'
        A_AREA = 'A_AREA', 'Ally Area'
        GLOBAL = 'GLOBAL', 'Global'

    class EffectType(models.TextChoices):
        DAMAGE = 'DAMAGE', 'Deal Damage'
        HEAL = 'HEAL', 'Healing'
        EFFECT = 'EFFECT', 'Apply Effect'

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50) #Skill name
    description = models.TextField(blank=True) #Description of the skill

    # Requirement
    # Job having skill, null for skill all job or monster skill
    job = models.ForeignKey('classes.Job', on_delete=models.SET_NULL, null=True, blank=True, related_name='skills')
    required_level = models.IntegerField(default=1) #Level required to using the skill

    #Attribute
    mp_cost = models.IntegerField(default=0) #MP cost of the skill
    cooldown = models.IntegerField(default=0) #Cooldown of the skill

    #Type of ski;;
    target_type = models.CharField(max_length=10, choices=TargetType.choices, default=TargetType.ENEMY)
    effect_type = models.CharField(max_length=10, choices=EffectType.choices, default=EffectType.DAMAGE)

    base_power = models.FloatField(default=0) #Base power of the skill
    power_ratio = models.FloatField(default=0) #Power ratio based on character's damage

    applies_effect = models.ForeignKey('EffectTemplate', on_delete=models.SET_NULL, null=True, blank=True, help_text="Effect applied by the skill")
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class SpecialEffectTag(models.Model):
    """
    Tag for special effects that can be applied by skills
    """
    id = models.CharField(max_length=50, primary_key=True, help_text="Unique identifier for the special effect")
    name = models.CharField(max_length=100) #Name of the special effect
    description = models.TextField(blank=True) #Description of the special effect

    def __str__(self):
        return self.name


class EffectTemplate(models.Model):
    """
    Additional effects for skills
    """
    name = models.CharField(max_length=100) #Name of the effect
    description = models.TextField(blank=True) #Description of the effect
    duration_turns = models.IntegerField(default=1) #Duration in turns
    icon = models.ImageField(upload_to='images/icons/effects', null=True, blank=True) #Icon for the effect
    #Stacking
    class StackingRule(models.TextChoices):
        REFRESH = 'REFRESH', 'Refresh Duration'
        INDEPENDENT = 'INDEPENDENT', 'Independent Stacks'
        UPGRADE = 'UPGRADE', 'Upgrade Effect'
        NO_STACK = 'NO_STACK', 'No Stacking'
    stacking_rule = models.CharField(max_length=15, choices=StackingRule.choices, default=StackingRule.REFRESH)
    # Modifiers
    flat_hp_change = models.IntegerField(default=0) #Flat HP change, positive for buff, negative for debuff
    percent_hp_change = models.FloatField(default=0) #Percentage HP change, positive for buff, negative for debuff
    flat_mp_change = models.IntegerField(default=0) #Flat MP change, positive for buff, negative for debuff
    percent_mp_change = models.FloatField(default=0) #Percentage MP change, positive for buff, negative for debuff
    flat_att_change = models.IntegerField(default=0) #Attack change, positive for buff, negative for debuff
    percent_att_change = models.FloatField(default=0) #Percentage attack change, positive for buff, negative for debuff
    flat_str_change = models.IntegerField(default=0) #Strength change, positive for buff, negative for debuff
    percent_str_change = models.FloatField(default=0) #Percentage strength change, positive for buff, negative for debuff
    flat_agi_change = models.IntegerField(default=0) #Agility change, positive for buff, negative for debuff
    percent_agi_change = models.FloatField(default=0) #Percentage agility change, positive for buff, negative for debuff
    flat_int_change = models.IntegerField(default=0) #Intelligence change, positive for buff, negative for debuff
    percent_int_change = models.FloatField(default=0) #Percentage intelligence change, positive for buff, negative for debuff
    drop_rate_change = models.FloatField(default=0) #Drop rate change, positive for buff, negative for debuff
    exp_rate_change = models.FloatField(default=0) #EXP rate change, positive for buff, negative for debuff

    shields_points = models.IntegerField(default=0, help_text="Amount of damage the shield can absorb") #Amount of damage the shield can absorb
    cooldown_reduction = models.IntegerField(default=0, help_text="Reduction in skill cooldown in turns") #Reduction in skill cooldown in turns

    # Per turn effects
    hp_change_per_turn = models.IntegerField(default=0) #Flat HP change per turn, positive for buff, negative for debuff
    mp_change_per_turn = models.IntegerField(default=0) #Flat MP change per turn

    #Special effect tag
    damage_taken_modifier = models.FloatField(default=0, help_text="Modifier to damage taken, positive to increase damage taken, negative to reduce damage taken")
    damage_dealt_modifier = models.FloatField(default=0, help_text="Modifier to damage dealt, positive to increase damage dealt, negative to reduce damage dealt")
    health_received_modifier = models.FloatField(default=0, help_text="Modifier to health received from healing, positive to increase healing received, negative to reduce healing received")
    mana_received_modifier = models.FloatField(default=0, help_text="Modifier to mana received from mana restoration, positive to increase mana received, negative to reduce mana received")
    health_dealt_modifier = models.FloatField(default=0, help_text="Modifier to health dealt by caster, positive to increase health dealt, negative to reduce health dealt")
    mana_dealt_modifier = models.FloatField(default=0, help_text="Modifier to mana dealt by caster, positive to increase mana dealt, negative to reduce mana dealt")

    special_effects = models.ManyToManyField(SpecialEffectTag, blank=True, related_name='effects')
    dispellable = models.BooleanField(default=True) #If the effect can be dispelled


    def __str__(self):
        return self.name