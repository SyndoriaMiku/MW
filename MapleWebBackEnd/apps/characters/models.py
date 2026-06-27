from datetime import timedelta

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

    # Location in the world
    current_location = models.ForeignKey(
        'world.Location', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='characters_here',
        help_text="Character's current location in the world"
    )
    
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
            self.last_stamina_update += timedelta(seconds=seconds_used)
            self.save(update_fields=['current_stamina', 'last_stamina_update'])
        return self.current_stamina

    def _get_equipped_items(self):
        """Helper method to get all equipped InventoryItems via the dynamic equipment system."""
        if not hasattr(self, '_cached_equipment'):
            self._cached_equipment = [
                eq.item for eq in self.equipped_items.select_related(
                    'item__template', 'slot'
                ).all()
            ]
        return self._cached_equipment
    
    def _get_base_equipment_mods(self, mods, equipped_items):
        """Get stat from ItemTemplate."""
        for item in equipped_items:
            template = item.template
            mods['hp']['base_flat'] += template.hp_boost
            mods['mp']['base_flat'] += template.mp_boost
            mods['att']['base_flat'] += template.att_boost
            mods['str']['base_flat'] += template.str_boost
            mods['agi']['base_flat'] += template.agi_boost
            mods['int']['base_flat'] += template.int_boost

            if template.all_stats_boost > 0:
                for stat in ['str', 'agi', 'int']:
                    mods[stat]['base_flat'] += template.all_stats_boost
    
    def _get_lumen_ascend_mods(self, mods, equipped_items):
        """Get stat from Lumen Ascend. Stack all levels up to current."""
        from apps.items.models import LumenAscendRule
        for item in equipped_items:
            level = item.lumen_ascend_level
            if level > 0 and item.template.lumen_tier:
                rules = LumenAscendRule.objects.filter(
                    lumen_tier=item.template.lumen_tier, 
                    lumen_level__lte=level, 
                    item_type=item.template.item_type
                )
                for rule in rules:
                    mods['hp']['base_flat'] += rule.hp_boost
                    mods['mp']['base_flat'] += rule.mp_boost
                    mods['att']['base_flat'] += rule.att_boost
                    mods['str']['base_flat'] += rule.str_boost
                    mods['agi']['base_flat'] += rule.agi_boost
                    mods['int']['base_flat'] += rule.int_boost

    def _get_aurora_line_mods(self, mods, equipped_items):
        """Get stat from Aurora."""
        for item in equipped_items:
            for line in item.aurora_lines.all():
                stat, value = line.stat_type, line.value
                
                if stat == 'all':
                    for s in ['str', 'agi', 'int']:
                        if line.line_type == 'flat':
                            mods[s]['base_flat'] += value
                        elif line.line_type == 'percent':
                            mods[s]['percent'] += value / 100.0
                else:
                    # Map 'drop' to 'drop_rate' key in mods dict
                    stat_key = 'drop_rate' if stat == 'drop' else stat
                    if stat_key in mods:
                        if line.line_type == 'flat':
                            mods[stat_key]['base_flat'] += value
                        elif line.line_type == 'percent':
                            mods[stat_key]['percent'] += value / 100.0

    def _get_item_set_mods(self, mods, equipped_items):
        """Get stat from Item Set effects."""
        set_counts = defaultdict(int)
        for item in equipped_items:
            for item_set in item.template.item_sets.all():
                set_counts[item_set] += 1

        for item_set, count in set_counts.items():
            effects = item_set.effects.filter(required_count__lte=count)
            for effect in effects:
                mods['hp']['base_flat'] += effect.hp_boost
                mods['mp']['base_flat'] += effect.mp_boost
                mods['att']['base_flat'] += effect.att_boost
                mods['str']['base_flat'] += effect.str_boost
                mods['agi']['base_flat'] += effect.agi_boost
                mods['int']['base_flat'] += effect.int_boost
                
                if effect.all_stats_boost > 0:
                    for stat in ['str', 'agi', 'int']:
                        mods[stat]['base_flat'] += effect.all_stats_boost

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
    def total_final_damage(self):
        """
        Total final damage multiplier from active buffs.
        Placeholder for future buff system integration.
        Returns percentage (e.g. 0.2 for 20% bonus).
        """
        return 0.0

    @cached_property
    def total_damage(self):
        """
        Calculate base damage using the multiplicative formula:
        Base Damage = [(Main_Stat * Stat_Weight) * (Total_ATT * ATT_Weight)] / 100
        Char Damage = Base Damage * (1 + Char_Final_Damage)
        """
        if not self.job or not self.character_class:
            return self.total_att
        
        job = self.job
        main_stat = self.character_class.main_stat
        
        # Calculate Main Stat Value
        if main_stat == 'all':
            main_stat_value = self.total_str + self.total_agi + self.total_int
        else:
            stats = {
                "str": self.total_str,
                "agi": self.total_agi,
                "int": self.total_int,
            }
            main_stat_value = stats.get(main_stat, 0)
            
        # Step 1: Base Damage
        dmg_att = self.total_att * job.att_weight
        dmg_stat = main_stat_value * job.main_stat_weight
        base_damage = (dmg_stat * dmg_att) / 100.0
        
        # Step 2: Character Damage (amplified by final damage)
        char_damage = base_damage * (1 + self.total_final_damage)
        
        return round(char_damage)
        


    # ===================================================================
    # SECTION: PUBLIC STAT PROPERTIES
    # Cung cấp giao diện truy cập chỉ số cuối cùng một cách đơn giản.
    # ===================================================================

    @cached_property
    def total_str(self):
        mods = self._all_stat_modifiers['str']
        base = self.base_str + mods['base_flat']
        return round(base * (1 + mods['percent'])) + mods['extra_flat']

    @cached_property
    def total_agi(self):
        mods = self._all_stat_modifiers['agi']
        base = self.base_agi + mods['base_flat']
        return round(base * (1 + mods['percent'])) + mods['extra_flat']
        
    @cached_property
    def total_int(self):
        mods = self._all_stat_modifiers['int']
        base = self.base_int + mods['base_flat']
        return round(base * (1 + mods['percent'])) + mods['extra_flat']

    @cached_property
    def total_drop_rate(self):
        mods = self._all_stat_modifiers.get('drop_rate', {'base_flat': 0, 'percent': 0, 'extra_flat': 0})
        # Base drop rate modifier is 1.0 (100%), buffs add to it.
        return 1.0 + mods['base_flat'] + mods['percent'] + mods['extra_flat']

    @cached_property
    def total_exp_rate(self):
        mods = self._all_stat_modifiers.get('exp_rate', {'base_flat': 0, 'percent': 0, 'extra_flat': 0})
        # Base exp rate modifier is 1.0 (100%), buffs add to it.
        return 1.0 + mods['base_flat'] + mods['percent'] + mods['extra_flat']

    @cached_property
    def total_hp(self):
        mods = self._all_stat_modifiers['hp']
        base = self.base_hp + mods['base_flat']
        return round(base * (1 + mods['percent'])) + mods['extra_flat']

    @cached_property
    def total_mp(self):
        mods = self._all_stat_modifiers['mp']
        base = self.base_mp + mods['base_flat']
        return round(base * (1 + mods['percent'])) + mods['extra_flat']

    @cached_property
    def total_att(self):
        mods = self._all_stat_modifiers['att']
        base = self.base_att + mods['base_flat']
        return round(base * (1 + mods['percent'])) + mods['extra_flat']

    # ===================================================================
    # SECTION: LEVELING METHODS
    # ===================================================================

    def gain_exp(self, amount):
        """
        Add EXP and automatically level up if threshold is met.
        Uses ExperienceTable for thresholds and CharacterClass growth rates for stat gains.
        """
        from apps.world.models import ExperienceTable
        self.current_exp += amount

        leveled_up = False
        while True:
            try:
                exp_table = ExperienceTable.objects.get(level=self.level)
            except ExperienceTable.DoesNotExist:
                break  # Max level reached

            if self.current_exp >= exp_table.required_exp:
                self.current_exp -= exp_table.required_exp
                self._level_up()
                leveled_up = True
            else:
                break

        self.save(update_fields=[
            'level', 'current_exp',
            'base_hp', 'base_mp', 'base_str', 'base_agi', 'base_int'
        ])
        return leveled_up

    def _level_up(self):
        """Apply growth rates from CharacterClass when leveling up."""
        self.level += 1
        if self.character_class:
            cc = self.character_class
            self.base_hp += int(cc.hp_growth)
            self.base_mp += int(cc.mp_growth)
            self.base_str += int(cc.str_growth)
            self.base_agi += int(cc.agi_growth)
            self.base_int += int(cc.int_growth)


# ===================================================================
# SECTION: DYNAMIC EQUIPMENT SYSTEM
# ===================================================================

class EquipmentSlotConfig(models.Model):
    """
    Admin-configurable equipment slot definitions.
    Adding/removing/resizing slots requires NO code changes or migrations.
    """
    slot_type = models.CharField(
        max_length=30, unique=True,
        help_text="Internal identifier, e.g. 'hat', 'ring', 'weapon'"
    )
    display_name = models.CharField(
        max_length=50,
        help_text="Human-readable name, e.g. 'Hat', 'Ring', 'Weapon'"
    )
    max_count = models.PositiveIntegerField(
        default=1,
        help_text="How many items can be equipped in this slot type (e.g. 4 for rings)"
    )
    allowed_item_types = models.JSONField(
        default=list,
        help_text="List of item_type values allowed in this slot, e.g. ['hat'] or ['ring']"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order in equipment UI"
    )

    class Meta:
        verbose_name = "Equipment Slot Config"
        verbose_name_plural = "Equipment Slot Configs"
        ordering = ['order']

    def __str__(self):
        count_str = f" (x{self.max_count})" if self.max_count > 1 else ""
        return f"{self.display_name}{count_str}"


class EquippedItem(models.Model):
    """
    An item currently equipped on a character in a specific slot.
    """
    character = models.ForeignKey(
        Character, on_delete=models.CASCADE,
        related_name='equipped_items'
    )
    slot = models.ForeignKey(
        EquipmentSlotConfig, on_delete=models.CASCADE,
        related_name='equipped_items'
    )
    slot_index = models.PositiveIntegerField(
        default=0,
        help_text="Index within the slot (0 for single slots, 0-3 for 4-slot rings)"
    )
    item = models.OneToOneField(
        'inventory.InventoryItem', on_delete=models.CASCADE,
        related_name='equipped_in',
        help_text="The inventory item that is equipped"
    )

    class Meta:
        unique_together = ('character', 'slot', 'slot_index')
        verbose_name = "Equipped Item"
        verbose_name_plural = "Equipped Items"
        ordering = ['slot__order', 'slot_index']

    def __str__(self):
        return f"{self.character.name} [{self.slot.display_name}] = {self.item.template.name}"
    
class CharacterSkill(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='skills')
    skill_template = models.ForeignKey('skilles.SkillTemplate', on_delete=models.CASCADE)
    level = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])
    bonus_final_damage = models.FloatField(default=0.0, help_text="Bonus final damage multiplier for this specific skill (e.g. 0.2 for +20% dmg)")
    
    class Meta:
        unique_together = ('character', 'skill_template')
        verbose_name = "Character Skill"
        verbose_name_plural = "Character Skills"
        ordering = ['character', 'skill_template']
    
    def __str__(self):
        return f"{self.character.name} - {self.skill_template.name} (Level {self.level})"


    
        
