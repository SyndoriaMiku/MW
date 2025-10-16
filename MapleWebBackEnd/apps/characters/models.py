from django.db import models
from django.utils.functional import cached_property
from collections import defaultdict
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

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
    owner = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='characters')
    
    #stats
    
    base_hp = models.IntegerField(default=50) #base hp stat
    base_mp = models.IntegerField(default=5) #base mp stat
    base_att = models.IntegerField(default=5) #base attack stat
    base_str = models.IntegerField(default=10) #base strength stat
    base_agi = models.IntegerField(default=10) #base agility stat
    base_int = models.IntegerField(default=10) #base intelligence stat

    #drop rate
    drop_rate = models.FloatField(default=1) #100% base drop rate
    
    #information
    character_class = models.ForeignKey('classes.CharacterClass', on_delete=models.SET_NULL, null=True)
    job = models.ForeignKey('classes.Job', on_delete=models.SET_NULL, null=True)
    
    #leveling
    level = models.IntegerField(default=1)
    current_exp = models.IntegerField(default=0)

    #stamina system
    max_stamina = models.IntegerField(default=120)
    current_stamina = models.PositiveIntegerField(default=120, validators=[MinValueValidator(0), MaxValueValidator(120)])
    last_stamina_update = models.DateTimeField(default=timezone.now,help_text="Last time stamina was updated")

    
    def __str__(self):
        return self.name
    
    #Stamina regeneration logic
    STAMINA_REGEN_RATE = 180 #Regenerate 1 stamina every interval in seconds
    def update_stamina(self):
        """
        Calculate and update current stamina based on time elapsed since last update.
        Always call this method before accessing current_stamina.
        """
        if self.current_stamina >= self.max_stamina:
            self.last_stamina_update = timezone.now()
            self.save(update_fields=['last_stamina_update'])
            return self.current_stamina
        #Calculate time elapsed since last update
        now = timezone.now()
        time_passed = (now - self.last_stamina_update).total_seconds()
        #Calculate how much stamina to regenerate
        stamina_to_regen = int(time_passed // self.STAMINA_REGEN_RATE)
        if stamina_to_regen > 0:
            new_stamina = min(self.current_stamina + stamina_to_regen, self.max_stamina)
            self.current_stamina = new_stamina
            #Update last update time to account for partial intervals
            seconds_used = stamina_to_regen * self.STAMINA_REGEN_RATE
            self.last_stamina_update += timezone.timedelta(seconds=seconds_used)
            self.save(update_fields=['current_stamina', 'last_stamina_update'])
        return self.current_stamina

    def _get_equipped_items(self):
        """Helper method to get all equipped items."""
        if not hasattr(self, 'equipment'):
            return []
            
        if not hasattr(self, '_cached_equipment'):
            equipment = []
            slot_fields = [
                'hat', 'top', 'bottom', 'shoes', 'cape', 'gloves', 'shoulder',
                'weapon', 'face', 'eye', 'belt', 'earring', 'pendant'
            ]
            for field in slot_fields:
                item = getattr(self.equipment, field, None)
                if item:
                    equipment.append(item)
            equipment.extend(self.equipment.rings.all())
            self._cached_equipment = equipment
        return self._cached_equipment
    
    def _get_base_equipment_mods(self, mods, equipped_items):
        """Get stat from ItemTemplate."""
        for item in equipped_items:
            template = item.template
            mods['hp']['flat'] += template.hp_boost
            mods['mp']['flat'] += template.mp_boost
            mods['att']['flat'] += template.att_boost
            mods['str']['flat'] += template.str_boost
            mods['agi']['flat'] += template.agi_boost
            mods['int']['flat'] += template.int_boost

            if template.all_stats_boost > 0:
                for stat in ['str', 'agi', 'int']:
                    mods[stat]['flat'] += template.all_stats_boost
    
    def _get_lumen_ascend_mods(self, mods, equipped_items):
        """Get stat from Lumen Ascend."""
        from items.models import LumenAscendRule
        for item in equipped_items:
            level = item.lumen_ascend_level
            if level > 0 and item.template.lumen_tier:
                rules = LumenAscendRule.objects.filter(tier=item.template.lumen_tier, level=level, item_type=item.template.item_type)
                for rule in rules:
                    mods['hp']['flat'] += rule.hp_boost
                    mods['mp']['flat'] += rule.mp_boost
                    mods['att']['flat'] += rule.att_boost
                    mods['str']['flat'] += rule.str_boost
                    mods['agi']['flat'] += rule.agi_boost
                    mods['int']['flat'] += rule.int_boost

    def _get_aurora_line_mods(self, mods, equipped_items):
        """Get stat from Aurora."""
        for item in equipped_items:
            for line in item.aurora_lines.all():
                stat, value = line.stat_type, line.value
                
                if stat == 'all':
                    for s in ['str', 'agi', 'int']:
                        if line.line_type == 'flat':
                            mods[s]['flat'] += value
                        elif line.line_type == 'percent':
                            mods[s]['percent'] += value / 100.0
                elif stat in mods:
                    if line.line_type == 'flat':
                        mods[stat]['flat'] += value
                    elif line.line_type == 'percent':
                        mods[stat]['percent'] += value / 100.0

    def _get_item_set_mods(self, mods, equipped_items):
        """Get stat from Item Set effects."""
        set_counts = defaultdict(int)
        for item in equipped_items:
            for item_set in item.template.item_sets.all():
                set_counts[item_set] += 1

        for item_set, count in set_counts.items():
            effects = item_set.effects.filter(required_count__lte=count)
            for effect in effects:
                mods['hp']['flat'] += effect.hp_boost
                mods['mp']['flat'] += effect.mp_boost
                mods['att']['flat'] += effect.att_boost
                mods['str']['flat'] += effect.str_boost
                mods['agi']['flat'] += effect.agi_boost
                mods['int']['flat'] += effect.int_boost
                
                if effect.all_stats_boost > 0:
                    for stat in ['str', 'agi', 'int']:
                        mods[stat]['flat'] += effect.all_stats_boost

    @cached_property
    def _all_stat_modifiers(self):
        """
        Get all the bonus modifiers from equipment and other sources.
        """
        stat_keys = ['hp', 'mp', 'att', 'str', 'agi', 'int', 'drop_rate']
        mods = {key: {'flat': 0, 'percent': 0} for key in stat_keys}
        
        equipped_items = self._get_equipped_items()

        # --- GỌI CÁC LỚP TÍNH TOÁN THEO THỨ TỰ ---
        self._get_base_equipment_mods(mods, equipped_items)
        self._get_aurora_line_mods(mods, equipped_items)
        self._get_lumen_ascend_mods(mods, equipped_items)
        self._get_item_set_mods(mods, equipped_items)
        
        return mods
    @cached_property
    def total_damage(self):
        """
        Calculate total damage based on total stats and class ratios.
        """
        if not self.job or not self.character_class:
            return self.total_att
        
        job = self.job
        main_stat = self.character_class.main_stat
        stats = {
            "str": self.total_str,
            "agi": self.total_agi,
            "int": self.total_int,
        }
        total_main_stats = stats.pop(main_stat)

        dmg_att = self.total_att * job.att_weight
        dmg_stat = total_main_stats * job.main_stat_weight
        final_dmg = dmg_att + dmg_stat

        return round(final_dmg)
        


    # ===================================================================
    # SECTION: PUBLIC STAT PROPERTIES
    # Cung cấp giao diện truy cập chỉ số cuối cùng một cách đơn giản.
    # ===================================================================

    @cached_property
    def total_str(self):
        mods = self._all_stat_modifiers['str']
        return round((self.base_str + mods['flat']) * (1 + mods['percent']))

    @cached_property
    def total_agi(self):
        mods = self._all_stat_modifiers['agi']
        return round((self.base_agi + mods['flat']) * (1 + mods['percent']))
        
    @cached_property
    def total_int(self):
        mods = self._all_stat_modifiers['int']
        return round((self.base_int + mods['flat']) * (1 + mods['percent']))

    @cached_property
    def total_hp(self):
        mods = self._all_stat_modifiers['hp']
        return round((self.base_hp + mods['flat']) * (1 + mods['percent']))

    @cached_property
    def total_mp(self):
        mods = self._all_stat_modifiers['mp']
        return round((self.base_mp + mods['flat']) * (1 + mods['percent']))

    @cached_property
    def total_att(self):
        mods = self._all_stat_modifiers['att']
        return round((self.base_att + mods['flat']) * (1 + mods['percent']))
            
 
class Equipment(models.Model):
    character = models.OneToOneField(
        Character,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='equipment'
    )
    rings = models.ManyToManyField("inventory.InventoryItem",blank=True,related_name='+',limit_choices_to={'template__item_type': 'ring'})
    pendant = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='pendant_equipped')
    earring = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='earring_equipped')
    belt = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='belt_equipped')
    face = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='face_equipped')
    eye = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='eye_equipped')    
    hat = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='hat_equipped')
    top = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='top_equipped')
    bottom = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='bottom_equipped')
    shoes = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='shoes_equipped')
    cape = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='cape_equipped')
    gloves = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='gloves_equipped')
    shoulder = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='shoulder_equipped')
    weapon = models.ForeignKey("inventory.InventoryItem", on_delete=models.SET_NULL, null=True, blank=True, related_name='weapon_equipped')
    
    def __str__(self):
        return f"{self.character.name}'s Equipped"    
    
class CharacterSkill(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='skills')
    skill_template = models.ForeignKey('skills.SkillTemplate', on_delete=models.CASCADE)
    level = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])
    
    class Meta:
        unique_together = ('character', 'skill_template')
        verbose_name = "Character Skill"
        verbose_name_plural = "Character Skills"
        ordering = ['character', 'skill_template']
    
    def __str__(self):
        return f"{self.character.name} - {self.skill_template.name} (Level {self.level})"


    
        
