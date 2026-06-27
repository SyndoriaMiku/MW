import random
from django.db import transaction
from apps.items.models import (
    AuroraProperty, AuroraLinePool, AuroraModifierRule, AuroraEvent, ItemTemplate
)
from apps.inventory.models import InventoryItem, AuroraLine, PendingAuroraRoll

class AuroraService:
    @staticmethod
    def get_max_lines_for_item(item_template):
        """
        Determine the maximum number of Aurora lines based on item's minimum_level.
        < 60: 1 line
        60-99: 2 lines
        >= 100: 3 lines
        """
        lvl = item_template.minimum_level
        if lvl < 60:
            return 1
        elif lvl < 100:
            return 2
        else:
            return 3

    @staticmethod
    def get_active_tier_up_multiplier():
        events = AuroraEvent.objects.filter(is_active=True)
        multiplier = 1.0
        for event in events:
            if event.is_currently_active():
                multiplier *= event.tier_up_chance_multiplier
        return multiplier

    @staticmethod
    def _generate_random_line(aurora_property, item_type, aurora_level, line_index):
        """
        Pulls a random line from AuroraLinePool based on weights.
        Returns a dict of line data.
        """
        pools = AuroraLinePool.objects.filter(
            aurora_property=aurora_property,
            item_type=item_type,
            aurora_level=aurora_level
        )
        if not pools.exists():
            return None

        # Weighted random selection
        total_weight = sum(p.weight for p in pools)
        r = random.uniform(0, total_weight)
        current = 0
        selected_pool = None
        for p in pools:
            current += p.weight
            if r <= current:
                selected_pool = p
                break
        
        if not selected_pool:
            selected_pool = pools.first()

        return {
            'line_index': line_index,
            'stat_type': selected_pool.stat_type,
            'line_type': selected_pool.line_type,
            'value': selected_pool.value
        }

    @staticmethod
    def _generate_lines_for_item(inventory_item, count=None):
        """
        Generates `count` lines for an item. If count is None, generates max lines.
        Returns a list of dicts containing line data.
        """
        template = inventory_item.template
        if not template.aurora_tier:
            return []

        max_lines = AuroraService.get_max_lines_for_item(template)
        if count is None:
            count = max_lines

        item_type = template.item_type
        aurora_level = inventory_item.aurora_level
        if aurora_level == 0:
            aurora_level = 1 # Minimum level to have lines

        generated = []
        for i in range(count):
            line_idx = i % max_lines # Wrap around for triple choice
            line_data = AuroraService._generate_random_line(template.aurora_tier, item_type, aurora_level, line_idx)
            if line_data:
                generated.append(line_data)

        return generated

    @staticmethod
    @transaction.atomic
    def reveal_aurora(user, inventory_item_id):
        """
        First time revealing lines for an item.
        """
        try:
            item = InventoryItem.objects.get(id=inventory_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Item not found."}

        if item.aurora_lines.exists():
            return {"success": False, "message": "Item already has Aurora lines revealed."}

        if not item.template.aurora_tier:
            return {"success": False, "message": "Item cannot have Aurora lines."}

        # Set initial level to 1 if it's 0
        if item.aurora_level == 0:
            item.aurora_level = 1
            item.save(update_fields=['aurora_level'])

        lines_data = AuroraService._generate_lines_for_item(item)
        
        # Save lines to DB
        for data in lines_data:
            AuroraLine.objects.create(
                inventory_item=item,
                line_index=data['line_index'],
                stat_type=data['stat_type'],
                line_type=data['line_type'],
                value=data['value']
            )

        return {"success": True, "message": "Aurora lines revealed successfully."}

    @staticmethod
    @transaction.atomic
    def apply_modifier(user, target_item_id, modifier_item_id=None, use_lumis=False, target_line_index=None):
        """
        Apply a modifier (Cube/Scroll) or use Lumis to reroll.
        """
        try:
            target_item = InventoryItem.objects.get(id=target_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Target item not found."}

        if not target_item.template.aurora_tier:
            return {"success": False, "message": "Item does not support Aurora."}
            
        if target_item.aurora_level == 0:
            return {"success": False, "message": "Item must be revealed first."}

        # Check if there's a pending roll
        if hasattr(target_item, 'pending_aurora_roll'):
            return {"success": False, "message": "Please confirm or discard your pending roll first."}

        max_lines = AuroraService.get_max_lines_for_item(target_item.template)

        # -------------------------------------------------------------------
        # LUMIS REROLL
        # -------------------------------------------------------------------
        if use_lumis:
            cost = 500 # Define cost logic later
            if user.lumis < cost:
                return {"success": False, "message": f"Not enough Lumis. Need {cost}."}
            user.lumis -= cost
            user.save(update_fields=['lumis'])

            # Lumis roll is REROLL_ALL without tier-up chance
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines)
            
            # Delete old lines and save new ones immediately
            target_item.aurora_lines.all().delete()
            for data in new_lines:
                AuroraLine.objects.create(
                    inventory_item=target_item,
                    line_index=data['line_index'],
                    stat_type=data['stat_type'],
                    line_type=data['line_type'],
                    value=data['value']
                )
            return {"success": True, "message": "Rerolled successfully using Lumis.", "result": new_lines}

        # -------------------------------------------------------------------
        # ITEM REROLL (CUBES/SCROLLS)
        # -------------------------------------------------------------------
        if not modifier_item_id:
            return {"success": False, "message": "Must provide a modifier item or use Lumis."}

        try:
            modifier_item = InventoryItem.objects.get(id=modifier_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Modifier item not found."}

        if not hasattr(modifier_item.template, 'aurora_modifier_rule'):
            return {"success": False, "message": "This item is not a valid Aurora modifier."}

        rule = modifier_item.template.aurora_modifier_rule

        # Validate target max tier
        if target_item.aurora_level > rule.max_aurora_target.tier:
            return {"success": False, "message": "This item cannot be used on an item with this Aurora Level."}

        # Deduct modifier item
        modifier_item.quantity -= 1
        if modifier_item.quantity <= 0:
            modifier_item.delete()
        else:
            modifier_item.save(update_fields=['quantity'])

        # Check Tier Up
        tier_up_occurred = False
        if target_item.aurora_level < rule.max_aurora_target.tier:
            event_mult = AuroraService.get_active_tier_up_multiplier()
            final_chance = rule.tier_up_chance * event_mult
            if random.random() < final_chance:
                tier_up_occurred = True
                target_item.aurora_level += 1
                target_item.save(update_fields=['aurora_level'])

        mod_type = rule.modifier_type

        if mod_type == 'REROLL_ALL':
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines)
            target_item.aurora_lines.all().delete()
            for data in new_lines:
                AuroraLine.objects.create(
                    inventory_item=target_item,
                    line_index=data['line_index'],
                    stat_type=data['stat_type'],
                    line_type=data['line_type'],
                    value=data['value']
                )
            msg = "Rerolled successfully."
            if tier_up_occurred:
                msg = "TIER UP! " + msg
            return {"success": True, "message": msg, "tier_up": tier_up_occurred}

        elif mod_type == 'REROLL_CHOICE':
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines)
            PendingAuroraRoll.objects.create(
                inventory_item=target_item,
                modifier_type=mod_type,
                generated_lines_data=new_lines
            )
            msg = "Roll generated. Please choose to keep old or select new."
            if tier_up_occurred:
                msg = "TIER UP! " + msg
            return {"success": True, "message": msg, "pending": True, "new_lines": new_lines, "tier_up": tier_up_occurred}

        elif mod_type == 'REROLL_TRIPLE_CHOICE':
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines * 3)
            # Give each line a unique temp index for the frontend to pick from
            for idx, line in enumerate(new_lines):
                line['temp_id'] = idx
                
            PendingAuroraRoll.objects.create(
                inventory_item=target_item,
                modifier_type=mod_type,
                generated_lines_data=new_lines
            )
            return {"success": True, "message": "Select your desired lines.", "pending": True, "choices": new_lines}

        elif mod_type == 'REROLL_SINGLE':
            if target_line_index is None:
                return {"success": False, "message": "Must specify a target line index."}
            new_line = AuroraService._generate_random_line(target_item.template.aurora_tier, target_item.template.item_type, target_item.aurora_level, target_line_index)
            # Update immediately
            line_obj = target_item.aurora_lines.filter(line_index=target_line_index).first()
            if line_obj and new_line:
                line_obj.stat_type = new_line['stat_type']
                line_obj.line_type = new_line['line_type']
                line_obj.value = new_line['value']
                line_obj.save()
            return {"success": True, "message": f"Line {target_line_index} rerolled."}

        elif mod_type == 'REPLACE_FIXED':
            if target_line_index is None:
                return {"success": False, "message": "Must specify a target line index."}
            line_obj = target_item.aurora_lines.filter(line_index=target_line_index).first()
            if line_obj:
                line_obj.stat_type = rule.fixed_stat_type
                line_obj.line_type = rule.fixed_line_type
                line_obj.value = rule.fixed_value
                line_obj.save()
            return {"success": True, "message": f"Line {target_line_index} replaced with fixed stat."}

        elif mod_type == 'FORCE_SET':
            target_item.aurora_level = rule.forced_aurora_level
            target_item.save(update_fields=['aurora_level'])
            
            target_item.aurora_lines.all().delete()
            # Assuming force set just sets one fixed line for now, could be expanded to a list
            AuroraLine.objects.create(
                inventory_item=target_item,
                line_index=0,
                stat_type=rule.fixed_stat_type,
                line_type=rule.fixed_line_type,
                value=rule.fixed_value
            )
            return {"success": True, "message": "Item forced to fixed state."}

        return {"success": False, "message": "Modifier type not fully implemented."}

    @staticmethod
    @transaction.atomic
    def confirm_pending_roll(user, inventory_item_id, action, selected_temp_ids=None):
        """
        action: 'keep_old', 'take_new', 'select_specific'
        """
        try:
            item = InventoryItem.objects.get(id=inventory_item_id, owner__user=user)
            pending = item.pending_aurora_roll
        except (InventoryItem.DoesNotExist, PendingAuroraRoll.DoesNotExist):
            return {"success": False, "message": "No pending roll found."}

        if action == 'keep_old':
            pending.delete()
            return {"success": True, "message": "Kept old lines."}

        elif action == 'take_new' and pending.modifier_type == 'REROLL_CHOICE':
            item.aurora_lines.all().delete()
            for data in pending.generated_lines_data:
                AuroraLine.objects.create(
                    inventory_item=item,
                    line_index=data['line_index'],
                    stat_type=data['stat_type'],
                    line_type=data['line_type'],
                    value=data['value']
                )
            pending.delete()
            return {"success": True, "message": "New lines applied."}

        elif action == 'select_specific' and pending.modifier_type == 'REROLL_TRIPLE_CHOICE':
            if not selected_temp_ids or len(selected_temp_ids) != AuroraService.get_max_lines_for_item(item.template):
                return {"success": False, "message": "Invalid number of selections."}
                
            selected_lines = [l for l in pending.generated_lines_data if l['temp_id'] in selected_temp_ids]
            
            item.aurora_lines.all().delete()
            for idx, data in enumerate(selected_lines):
                AuroraLine.objects.create(
                    inventory_item=item,
                    line_index=idx, # Reassign index 0,1,2
                    stat_type=data['stat_type'],
                    line_type=data['line_type'],
                    value=data['value']
                )
            pending.delete()
            return {"success": True, "message": "Selected lines applied."}

        return {"success": False, "message": "Invalid action."}
