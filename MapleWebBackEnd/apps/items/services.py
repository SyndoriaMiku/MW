import random
from apps.items.models import LumenCostRule, LumenEvent
from apps.inventory.models import InventoryItem

class LumenService:
    @staticmethod
    def get_active_event_modifiers():
        """
        Combine modifiers from all currently active LumenEvents.
        Returns: (success_bonus, heavy_fail_mult, bonus_lvls)
        """
        events = LumenEvent.objects.filter(is_active=True)
        success_bonus = 0.0
        heavy_fail_mult = 1.0
        bonus_lvls = 0
        
        for event in events:
            if event.is_currently_active():
                success_bonus += event.success_flat_bonus
                heavy_fail_mult *= event.heavy_failure_multiplier
                bonus_lvls += event.bonus_levels
                
        return success_bonus, heavy_fail_mult, bonus_lvls

    @staticmethod
    def attempt_lumen_ascend(user, inventory_item_id):
        """
        Attempt to upgrade an item using the Lumen Ascend system.
        Returns a dictionary with success status, result, and message.
        """
        try:
            item = InventoryItem.objects.get(id=inventory_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Item not found or not owned."}

        if item.is_destroyed:
            return {"success": False, "message": "Item is a fragment and must be restored first."}

        if not item.template.lumen_tier:
            return {"success": False, "message": "Item cannot be upgraded."}

        current_level = item.lumen_ascend_level
        if current_level >= item.template.lumen_tier.max_lumen_level:
            return {"success": False, "message": "Item is already at max level."}

        try:
            rule = LumenCostRule.objects.get(lumen_tier=item.template.lumen_tier, current_level=current_level)
        except LumenCostRule.DoesNotExist:
            return {"success": False, "message": "Upgrade rule not found for this level."}

        # Check Lumis cost
        if user.lumis < rule.lumis_cost:
            return {"success": False, "message": f"Not enough Lumis. Need {rule.lumis_cost}."}

        # Deduct Lumis
        user.lumis -= rule.lumis_cost
        user.save(update_fields=['lumis'])

        # Get Event Modifiers
        success_bonus, heavy_fail_mult, bonus_lvls = LumenService.get_active_event_modifiers()

        # Calculate Final Rates and ensure total sum is exactly 1.0 (100%)
        # 1. Apply success bonus (max 100%)
        final_success = min(1.0, rule.success_rate + success_bonus)
        
        # 2. Apply heavy failure multiplier
        final_heavy = rule.heavy_failure_rate * heavy_fail_mult
        
        # 3. Ensure success + heavy does not exceed 100%
        if final_success + final_heavy > 1.0:
            final_heavy = 1.0 - final_success
            
        # 4. The remainder is normal failure
        final_fail = 1.0 - (final_success + final_heavy)

        # Roll the dice (0.0 to 1.0)
        roll = random.random()

        if roll < final_success:
            # Success
            levels_gained = 1 + bonus_lvls
            item.lumen_ascend_level = min(item.template.lumen_tier.max_lumen_level, item.lumen_ascend_level + levels_gained)
            item.save(update_fields=['lumen_ascend_level'])
            return {
                "success": True, 
                "result": "success", 
                "message": f"Upgrade successful! Level increased to {item.lumen_ascend_level}."
            }
        
        elif roll < final_success + final_heavy:
            # Heavy Failure (Boom -> Fragment)
            item.is_destroyed = True
            item.save(update_fields=['is_destroyed'])
            
            # Unequip if equipped
            if hasattr(item, 'equipped_in'):
                item.equipped_in.delete()
                
            return {
                "success": True, 
                "result": "heavy_failure", 
                "message": "Heavy Failure! Item has been destroyed into a fragment."
            }
        
        else:
            # Normal Failure (Level remains the same)
            # This corresponds to the remaining probability (final_fail)
            return {
                "success": True, 
                "result": "failure", 
                "message": "Upgrade failed. Item level remains the same."
            }

    @staticmethod
    def restore_fragment(user, fragment_item_id, sacrifice_item_id=None):
        """
        Restore a destroyed item (fragment) using a sacrifice item (phôi trắng).
        Note: Logic for restoring via special points/items during events can be added here in the future.
        """
        try:
            fragment = InventoryItem.objects.get(id=fragment_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Fragment not found."}

        if not fragment.is_destroyed:
            return {"success": False, "message": "Item is not destroyed."}

        # Future Logic Hook: 
        # if use_special_event_item:
        #     deduct_item()
        #     restore()

        # Method: Using a Sacrifice Item (Phôi)
        if sacrifice_item_id:
            try:
                sacrifice = InventoryItem.objects.get(id=sacrifice_item_id, owner__user=user)
            except InventoryItem.DoesNotExist:
                return {"success": False, "message": "Sacrifice item not found."}

            if sacrifice.is_destroyed:
                return {"success": False, "message": "Cannot use a destroyed item as a sacrifice."}

            if sacrifice.template != fragment.template:
                return {"success": False, "message": "Sacrifice item must be the exact same type (same template)."}

            if sacrifice.lumen_ascend_level > 0 or sacrifice.aurora_level > 0:
                return {"success": False, "message": "Sacrifice item must be a clean/base item (no upgrades)."}

            # Consume sacrifice and restore fragment
            sacrifice.delete()
            
            fragment.is_destroyed = False
            fragment.save(update_fields=['is_destroyed'])
            return {"success": True, "message": "Fragment restored successfully using a sacrifice item!"}
            
        return {"success": False, "message": "Must provide a sacrifice item to restore the fragment."}
