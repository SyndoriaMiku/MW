import random
from django.db import transaction
from django.db.models import F
from apps.items.models import (
    AuroraProperty, AuroraLinePool, AuroraModifierRule, AuroraEvent, ItemTemplate, AuroraLineCountConfig
)
from apps.inventory.models import InventoryItem, AuroraLine, PendingAuroraRoll

class AuroraService:
    @staticmethod
    def get_max_lines_for_item(item_template):
        """
        Return the maximum number of Aurora lines configured globally based on minimum level.
        """
        lvl = item_template.minimum_level
        config = AuroraLineCountConfig.objects.filter(min_item_level__lte=lvl).first()
        if config:
            return config.max_lines
        return 1

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
        pools_queryset = AuroraLinePool.objects.filter(
            aurora_property=aurora_property,
            aurora_level=aurora_level
        )
        pools = [p for p in pools_queryset if item_type in p.item_types]
        if not pools:
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
            selected_pool = pools[0]

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
        # (C-3 fix) Lock item row to prevent concurrent reveals creating duplicate lines
        try:
            item = InventoryItem.objects.select_for_update().get(id=inventory_item_id, owner__user=user)
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
        expected_lines = AuroraService.get_max_lines_for_item(item.template)
        if len(lines_data) != expected_lines:
            transaction.set_rollback(True)
            return {"success": False, "message": "No complete Aurora line pool is configured for this item."}
        
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
        # (C-3 fix) Lock target item row — prevents concurrent cube usage on same item
        try:
            target_item = InventoryItem.objects.select_for_update().get(id=target_item_id, owner__user=user)
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
            # (C-3 fix) Lock user row and re-check balance under lock
            from apps.users.models import GameUser
            locked_user = GameUser.objects.select_for_update().get(pk=user.pk)
            if locked_user.lumis < cost:
                return {"success": False, "message": f"Not enough Lumis. Need {cost}."}
            # (C-3 fix) Use F() for atomic deduction
            GameUser.objects.filter(pk=locked_user.pk).update(lumis=F('lumis') - cost)

            # Lumis roll is REROLL_ALL without tier-up chance
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines)
            if len(new_lines) != max_lines:
                transaction.set_rollback(True)
                return {"success": False, "message": "No complete Aurora line pool is configured for this item."}
            
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
            # (C-3 fix) Lock modifier item — prevents same cube being used in concurrent requests
            modifier_item = InventoryItem.objects.select_for_update().get(id=modifier_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Modifier item not found."}

        if not hasattr(modifier_item.template, 'aurora_modifier_rule'):
            return {"success": False, "message": "This item is not a valid Aurora modifier."}

        rule = modifier_item.template.aurora_modifier_rule
        mod_type = rule.modifier_type

        if modifier_item.pk == target_item.pk:
            return {"success": False, "message": "The target item cannot also be the modifier item."}
        if modifier_item.quantity <= 0:
            return {"success": False, "message": "Modifier item has no remaining quantity."}

        implemented_types = {
            'REROLL_ALL', 'REROLL_CHOICE', 'REROLL_TRIPLE_CHOICE',
            'REROLL_SINGLE', 'REPLACE_FIXED', 'FORCE_SET',
        }
        if mod_type not in implemented_types:
            return {"success": False, "message": "This modifier type is not implemented."}

        if mod_type in {'REROLL_SINGLE', 'REPLACE_FIXED'}:
            if target_line_index is None:
                return {"success": False, "message": "Must specify a target line index."}
            try:
                target_line_index = int(target_line_index)
            except (TypeError, ValueError):
                return {"success": False, "message": "Target line index must be an integer."}
            if target_line_index < 0 or target_line_index >= max_lines:
                return {"success": False, "message": "Target line index is out of range."}
            if not target_item.aurora_lines.filter(line_index=target_line_index).exists():
                return {"success": False, "message": "Target Aurora line does not exist."}

        if mod_type in {'REPLACE_FIXED', 'FORCE_SET'}:
            if rule.fixed_stat_type is None or rule.fixed_line_type is None or rule.fixed_value is None:
                return {"success": False, "message": "Modifier fixed-line configuration is incomplete."}

        if mod_type == 'FORCE_SET':
            max_aurora_level = target_item.template.aurora_tier.max_aurora_level
            if (
                rule.forced_aurora_level is None
                or rule.forced_aurora_level < 1
                or rule.forced_aurora_level > max_aurora_level
            ):
                return {"success": False, "message": "Forced Aurora level is invalid for this item."}

        # Validate target max tier
        if target_item.aurora_level > rule.max_aurora_target:
            return {"success": False, "message": "This item cannot be used on an item with this Aurora Level."}

        # Deduct modifier item
        modifier_item.quantity -= 1
        if modifier_item.quantity <= 0:
            modifier_item.delete()
        else:
            modifier_item.save(update_fields=['quantity'])

        # Check Tier Up
        tier_up_occurred = False
        if target_item.aurora_level < rule.max_aurora_target:
            event_mult = AuroraService.get_active_tier_up_multiplier()
            final_chance = min(1.0, max(0.0, rule.tier_up_chance * event_mult))
            if random.random() < final_chance:
                tier_up_occurred = True
                target_item.aurora_level += 1
                target_item.save(update_fields=['aurora_level'])

        if mod_type == 'REROLL_ALL':
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines)
            if len(new_lines) != max_lines:
                transaction.set_rollback(True)
                return {"success": False, "message": "No complete Aurora line pool is configured for this item."}
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
            return {"success": True, "message": msg, "tier_up": tier_up_occurred, "new_lines": new_lines}

        elif mod_type == 'REROLL_CHOICE':
            new_lines = AuroraService._generate_lines_for_item(target_item, count=max_lines)
            if len(new_lines) != max_lines:
                transaction.set_rollback(True)
                return {"success": False, "message": "No complete Aurora line pool is configured for this item."}
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
            if len(new_lines) != max_lines * 3:
                transaction.set_rollback(True)
                return {"success": False, "message": "No complete Aurora line pool is configured for this item."}
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
            new_line = AuroraService._generate_random_line(target_item.template.aurora_tier, target_item.template.item_type, target_item.aurora_level, target_line_index)
            if new_line is None:
                transaction.set_rollback(True)
                return {"success": False, "message": "No Aurora line pool is configured for this item."}
            # Update immediately
            line_obj = target_item.aurora_lines.get(line_index=target_line_index)
            line_obj.stat_type = new_line['stat_type']
            line_obj.line_type = new_line['line_type']
            line_obj.value = new_line['value']
            line_obj.save()
            return {"success": True, "message": f"Line {target_line_index} rerolled."}

        elif mod_type == 'REPLACE_FIXED':
            line_obj = target_item.aurora_lines.get(line_index=target_line_index)
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

        transaction.set_rollback(True)
        return {"success": False, "message": "Modifier type not fully implemented."}

    @staticmethod
    @transaction.atomic
    def confirm_pending_roll(user, inventory_item_id, action, selected_temp_ids=None):
        """
        action: 'keep_old', 'take_new', 'select_specific'
        """
        # (C-3 fix) Lock item row to prevent concurrent confirm requests
        try:
            item = InventoryItem.objects.select_for_update().get(id=inventory_item_id, owner__user=user)
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
            expected_count = AuroraService.get_max_lines_for_item(item.template)
            if (
                not isinstance(selected_temp_ids, list)
                or len(selected_temp_ids) != expected_count
                or len(set(selected_temp_ids)) != expected_count
            ):
                return {"success": False, "message": "Invalid number of selections."}
                
            selected_lines = [l for l in pending.generated_lines_data if l['temp_id'] in selected_temp_ids]
            if len(selected_lines) != expected_count:
                return {"success": False, "message": "One or more selected lines are invalid."}
            
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
