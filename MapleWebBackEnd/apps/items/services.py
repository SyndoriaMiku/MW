import random
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.items.models import LumenCostRule, LumenEvent
from apps.inventory.models import InventoryItem
from apps.inventory.reservations import character_in_active_battle, mutation_block_reason

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
    def calculate_final_rates(rule):
        """Return the effective rates and event modifiers used by preview and roll."""
        success_bonus, heavy_fail_mult, bonus_lvls = (
            LumenService.get_active_event_modifiers()
        )
        final_success = max(0.0, min(1.0, rule.success_rate + success_bonus))
        final_heavy = max(0.0, rule.heavy_failure_rate * heavy_fail_mult)
        final_heavy = min(final_heavy, 1.0 - final_success)
        final_failure = max(0.0, 1.0 - final_success - final_heavy)
        # Keep JSON responses stable and readable instead of exposing binary-float
        # artifacts such as 0.20000000000000004.
        final_success = round(final_success, 10)
        final_heavy = round(final_heavy, 10)
        final_failure = round(final_failure, 10)
        return {
            'success': final_success,
            'failure': final_failure,
            'heavy_failure': final_heavy,
            'success_flat_bonus': success_bonus,
            'heavy_failure_multiplier': heavy_fail_mult,
            'bonus_levels': bonus_lvls,
        }

    @staticmethod
    def get_ascend_preview(user, inventory_item_id):
        """Return the exact current cost and rates without mutating the item."""
        try:
            item = InventoryItem.objects.select_related(
                'template__lumen_tier'
            ).get(id=inventory_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Item not found or not owned."}

        if item.is_destroyed:
            return {"success": False, "message": "Item is a fragment and must be restored first."}
        blocked_reason = mutation_block_reason(item)
        if blocked_reason:
            return {"success": False, "message": blocked_reason}
        if not item.template.lumen_tier:
            return {"success": False, "message": "Item cannot be upgraded."}
        if item.template.item_type in ['use', 'etc']:
            return {"success": False, "message": "Consume and Etc items cannot be upgraded."}

        tier = item.template.lumen_tier
        current_level = item.lumen_ascend_level
        if current_level >= tier.max_lumen_level:
            return {"success": False, "message": "Item is already at max level."}
        try:
            rule = LumenCostRule.objects.get(
                lumen_tier=tier, current_level=current_level
            )
        except LumenCostRule.DoesNotExist:
            return {"success": False, "message": "Upgrade rule not found for this level."}

        rates = LumenService.calculate_final_rates(rule)
        active_events = [
            {
                'id': event.id,
                'name': event.name,
                'success_flat_bonus': event.success_flat_bonus,
                'heavy_failure_multiplier': event.heavy_failure_multiplier,
                'bonus_levels': event.bonus_levels,
            }
            for event in LumenEvent.objects.filter(is_active=True)
            if event.is_currently_active()
        ]
        final_rates = {
            key: rates[key] for key in ('success', 'failure', 'heavy_failure')
        }
        return {
            'success': True,
            'inventory_item_id': item.id,
            'item_name': item.template.name,
            'tier': {
                'id': tier.id,
                'name': tier.name,
                'tier': tier.tier,
            },
            'level': {
                'current': current_level,
                'on_success': min(
                    tier.max_lumen_level,
                    current_level + max(1, 1 + rates['bonus_levels']),
                ),
                'max': tier.max_lumen_level,
            },
            'cost': {
                'currency': 'lumis',
                'amount': rule.lumis_cost,
                'balance': user.lumis,
                'can_afford': user.lumis >= rule.lumis_cost,
            },
            'base_rates': {
                'success': rule.success_rate,
                'failure': rule.failure_rate,
                'heavy_failure': rule.heavy_failure_rate,
            },
            'event_modifiers': {
                'success_flat_bonus': rates['success_flat_bonus'],
                'heavy_failure_multiplier': rates['heavy_failure_multiplier'],
                'bonus_levels': rates['bonus_levels'],
                'active_events': active_events,
            },
            'final_rates': final_rates,
            'final_rate_percent': {
                key: round(value * 100, 4)
                for key, value in final_rates.items()
            },
            'outcomes': {
                'success': 'level_up',
                'failure': 'no_change',
                'heavy_failure': 'item_destroyed',
            },
        }

    @staticmethod
    @transaction.atomic
    def attempt_lumen_ascend(user, inventory_item_id):
        """
        Attempt to upgrade an item using the Lumen Ascend system.
        Returns a dictionary with success status, result, and message.
        """
        # (RC-1/TS-2 fix) Lock user row to prevent double-click currency exploit
        from apps.users.models import GameUser
        user = GameUser.objects.select_for_update().get(pk=user.pk)

        try:
            item = InventoryItem.objects.select_for_update().get(id=inventory_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Item not found or not owned."}

        if item.is_destroyed:
            return {"success": False, "message": "Item is a fragment and must be restored first."}

        # A heavy failure unequips the item, and a listed or traded item must
        # reach its buyer/partner exactly as offered.
        if character_in_active_battle(getattr(user, 'character', None)):
            return {"success": False, "message": "Cannot use Lumen Ascend during an active battle."}
        blocked_reason = mutation_block_reason(item)
        if blocked_reason:
            return {"success": False, "message": blocked_reason}

        if not item.template.lumen_tier:
            return {"success": False, "message": "Item cannot be upgraded."}

        if item.template.item_type in ['use', 'etc']:
            return {"success": False, "message": "Consume and Etc items cannot be upgraded."}

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

        rates = LumenService.calculate_final_rates(rule)
        final_success = rates['success']
        final_heavy = rates['heavy_failure']
        bonus_lvls = rates['bonus_levels']

        # Roll the dice (0.0 to 1.0)
        roll = random.random()

        if roll < final_success:
            # Success
            levels_gained = max(1, 1 + bonus_lvls)
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
            return {
                "success": True, 
                "result": "failure", 
                "message": "Upgrade failed. Item level remains the same."
            }

    @staticmethod
    @transaction.atomic
    def apply_level_modifier(user, target_item_id, modifier_item_id):
        """
        Use an item with a LumenModifierRule to set gear straight to the rule's
        Lumen level. Always succeeds; it never lowers a level.
        """
        from apps.items.models import LumenModifierRule

        try:
            # lumen_tier is nullable, and PostgreSQL refuses FOR UPDATE on the
            # nullable side of an outer join: lock only the item row.
            target = InventoryItem.objects.select_for_update(of=('self',)).select_related(
                'template__lumen_tier'
            ).get(id=target_item_id, owner__user=user)
            modifier = InventoryItem.objects.select_for_update().select_related(
                'template'
            ).get(id=modifier_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Item not found or not owned."}
        if target.pk == modifier.pk:
            return {"success": False, "message": "The target item cannot also be the modifier item."}

        if character_in_active_battle(getattr(user, 'character', None)):
            return {"success": False, "message": "Cannot use Lumen items during an active battle."}
        # Only wearable gear: equipment that is neither destroyed nor expired.
        if target.template.is_stackable:
            return {"success": False, "message": "Only gear can be upgraded."}
        blocked_reason = mutation_block_reason(target, role='Target item')
        if blocked_reason:
            return {"success": False, "message": blocked_reason}
        blocked_reason = mutation_block_reason(modifier, role='Modifier item')
        if blocked_reason:
            return {"success": False, "message": blocked_reason}

        try:
            rule = modifier.template.lumen_modifier_rule
        except LumenModifierRule.DoesNotExist:
            return {"success": False, "message": "This item is not a Lumen modifier."}

        tier = target.template.lumen_tier
        if tier is None:
            return {"success": False, "message": "Item cannot be upgraded."}
        allowed_tiers = list(rule.lumen_tiers.all())
        if allowed_tiers and tier not in allowed_tiers:
            return {"success": False, "message": "This modifier does not work on this item's Lumen tier."}
        if rule.item_types and target.template.item_type not in rule.item_types:
            return {"success": False, "message": "This modifier does not work on this item type."}
        if rule.target_level > tier.max_lumen_level:
            return {"success": False, "message": "The modifier's level exceeds this item's maximum."}
        if target.lumen_ascend_level >= rule.target_level:
            return {"success": False, "message": f"Item is already at Lumen level {target.lumen_ascend_level}."}

        modifier.quantity -= 1
        if modifier.quantity <= 0:
            modifier.delete()
        else:
            modifier.save(update_fields=['quantity'])
        target.lumen_ascend_level = rule.target_level
        target.save(update_fields=['lumen_ascend_level'])
        return {
            "success": True,
            "message": f"Lumen level set to {rule.target_level}.",
            "lumen_ascend_level": rule.target_level,
        }

    @staticmethod
    @transaction.atomic
    def restore_fragment(user, fragment_item_id, sacrifice_item_id=None, restore_item_id=None):
        """
        Restore a destroyed item (fragment) with exactly one of:
        - a sacrifice item (phôi trắng): a clean copy of the same template;
        - a restore item: one item with a FragmentRestoreRule covering it.
        The gear keeps its Lumen level either way.
        """
        if bool(sacrifice_item_id) == bool(restore_item_id):
            return {"success": False, "message": "Provide either a sacrifice item or a restore item."}

        # (C-2 fix) Lock fragment row first to prevent concurrent restores
        try:
            fragment = InventoryItem.objects.select_for_update().get(id=fragment_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Fragment not found."}

        if not fragment.is_destroyed:
            return {"success": False, "message": "Item is not destroyed."}
        if fragment.expired_at and fragment.expired_at <= timezone.now():
            return {"success": False, "message": "Fragment is expired."}

        if restore_item_id:
            return LumenService._restore_with_item(user, fragment, restore_item_id)

        try:
            # (C-2 fix) Lock sacrifice row — prevents same item being used in concurrent restores
            sacrifice = InventoryItem.objects.select_for_update().get(id=sacrifice_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Sacrifice item not found."}

        if sacrifice.is_destroyed:
            return {"success": False, "message": "Cannot use a destroyed item as a sacrifice."}
        if hasattr(sacrifice, 'equipped_in'):
            return {"success": False, "message": "Equipped items cannot be used as a sacrifice."}
        blocked_reason = mutation_block_reason(sacrifice, role='Sacrifice item')
        if blocked_reason:
            return {"success": False, "message": blocked_reason}

        if sacrifice.template != fragment.template:
            return {"success": False, "message": "Sacrifice item must be the exact same type (same template)."}

        if sacrifice.lumen_ascend_level > 0 or sacrifice.aurora_level > 0:
            return {"success": False, "message": "Sacrifice item must be a clean/base item (no upgrades)."}

        sacrifice.delete()
        fragment.is_destroyed = False
        fragment.save(update_fields=['is_destroyed'])
        return {"success": True, "message": "Fragment restored successfully using a sacrifice item!"}

    @staticmethod
    def _restore_with_item(user, fragment, restore_item_id):
        """Consume one restore item on a locked fragment and restore it."""
        from apps.items.models import FragmentRestoreRule

        try:
            restore_item = InventoryItem.objects.select_for_update().select_related(
                'template'
            ).get(id=restore_item_id, owner__user=user)
        except InventoryItem.DoesNotExist:
            return {"success": False, "message": "Restore item not found."}
        blocked_reason = mutation_block_reason(restore_item, role='Restore item')
        if blocked_reason:
            return {"success": False, "message": blocked_reason}

        try:
            rule = restore_item.template.fragment_restore_rule
        except FragmentRestoreRule.DoesNotExist:
            return {"success": False, "message": "This item cannot restore fragments."}
        restorable = rule.restorable_items.all()
        if restorable.exists() and not restorable.filter(pk=fragment.template_id).exists():
            return {"success": False, "message": "This item cannot restore that fragment."}

        restore_item.quantity -= 1
        if restore_item.quantity <= 0:
            restore_item.delete()
        else:
            restore_item.save(update_fields=['quantity'])
        fragment.is_destroyed = False
        fragment.save(update_fields=['is_destroyed'])
        return {"success": True, "message": f"Fragment restored with {restore_item.template.name}."}

