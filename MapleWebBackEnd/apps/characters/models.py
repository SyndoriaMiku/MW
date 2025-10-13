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
    
    base_hp = models.IntegerField(default=50) #base hp stat
    base_mp = models.IntegerField(default=5) #base mp stat
    base_att = models.IntegerField(default=5) #base attack stat
    base_str = models.IntegerField(default=10) #base strength stat
    base_agi = models.IntegerField(default=10) #base agility stat
    base_int = models.IntegerField(default=10) #base intelligence stat

    #drop rate
    drop_rate = models.FloatField(default=1) #100% base drop rate
    
    #information
    character_class = models.ForeignKey('CharacterClass', on_delete=models.SET_NULL, null=True)
    Job = models.ForeignKey('Job', on_delete=models.SET_NULL, null=True)
    
    #leveling
    level = models.IntegerField(default=1)
    current_exp = models.IntegerField(default=0)
    
    def __str__(self):
        return self.name
    
    def _get_equipment(self):
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
        """Lớp 1: Thu thập chỉ số gốc từ ItemTemplate."""
        for item in equipped_items:
            template = item.template
            mods['hp']['flat'] += template.hp_boost
            mods['mp']['flat'] += template.mp_boost
            mods['att']['flat'] += template.att_boost
            mods['strength']['flat'] += template.strength_boost
            mods['agility']['flat'] += template.agility_boost
            mods['intelligence']['flat'] += template.intelligence_boost

            if template.all_stats_boost > 0:
                for stat in ['strength', 'agility', 'intelligence']:
                    mods[stat]['flat'] += template.all_stats_boost

    def _get_aurora_line_mods(self, mods, equipped_items):
        """Lớp 2: Thu thập chỉ số từ các dòng Aurora."""
        for item in equipped_items:
            for line in item.aurora_lines.all():
                stat, value = line.stat_type, line.value
                
                if stat == 'all':
                    for s in ['strength', 'agility', 'intelligence']:
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
        """Lớp 3: Thu thập chỉ số từ hiệu ứng Item Set."""
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
                mods['strength']['flat'] += effect.strength_boost
                mods['agility']['flat'] += effect.agility_boost
                mods['intelligence']['flat'] += effect.intelligence_boost
                
                if effect.all_stats_boost > 0:
                    for stat in ['strength', 'agility', 'intelligence']:
                        mods[stat]['flat'] += effect.all_stats_boost

    @cached_property
    def _all_stat_modifiers(self):
        """
        HÀM ĐIỀU PHỐI TRUNG TÂM: Chạy pipeline để lấy TẤT CẢ các bonus.
        """
        stat_keys = ['hp', 'mp', 'att', 'strength', 'agility', 'intelligence', 'drop_rate']
        mods = {key: {'flat': 0, 'percent': 0} for key in stat_keys}
        
        equipped_items = self._get_equipped_items()

        # --- GỌI CÁC LỚP TÍNH TOÁN THEO THỨ TỰ ---
        self._get_base_equipment_mods(mods, equipped_items)
        self._get_aurora_line_mods(mods, equipped_items)
        self._get_item_set_mods(mods, equipped_items)
        
        # TƯƠNG LAI: Thêm hàm mới ở đây, ví dụ:
        # self._get_lumen_ascend_mods(mods, equipped_items)
        # self._get_active_buff_mods(mods)
        
        return mods

    # ===================================================================
    # SECTION: PUBLIC STAT PROPERTIES
    # Cung cấp giao diện truy cập chỉ số cuối cùng một cách đơn giản.
    # ===================================================================

    @cached_property
    def total_strength(self):
        mods = self._all_stat_modifiers['strength']
        return round((self.base_strength + mods['flat']) * (1 + mods['percent']))

    @cached_property
    def total_agility(self):
        mods = self._all_stat_modifiers['agility']
        return round((self.base_agility + mods['flat']) * (1 + mods['percent']))
        
    @cached_property
    def total_intelligence(self):
        mods = self._all_stat_modifiers['intelligence']
        return round((self.base_intelligence + mods['flat']) * (1 + mods['percent']))

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
    weapon = models.ForeignKey("inventory.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name='weapon_equipped')
    
    def __str__(self):
        return f"{self.character.name}'s Equipped"    


    
        
