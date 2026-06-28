import random
from apps.battles.models import CombatInstance
from apps.inventory.models import InventoryItem
from apps.party.models import PendingPartyLoot

class RewardService:
    
    @staticmethod
    def process_battle_rewards(combat_instance: CombatInstance) -> dict:
        """
        Calculates and distributes rewards (EXP, Lumis, Items) for a victorious combat instance.
        """
        logs = {}
        
        # Get all defeated enemies in this instance
        defeated_enemies = [
            c.entity for c in combat_instance.combatants.filter(is_player=False, current_hp__lte=0)
        ]
        
        # Get all alive players in this instance
        alive_players = [
            c.entity for c in combat_instance.combatants.filter(is_player=True, current_hp__gt=0)
        ]
        
        if not alive_players or not defeated_enemies:
            return {"message": "No alive players or no defeated enemies."}
            
        # (S2 fix) Provision active quests for all alive players ONCE per battle
        from apps.quests.services import QuestService
        for player in alive_players:
            QuestService.get_active_quests(player)

        num_players = len(alive_players)

        # 1. Calculate Total EXP & Lumis pool
        total_exp = 0
        total_lumis = 0
        for enemy in defeated_enemies:
            total_exp += enemy.exp_reward
            total_lumis += random.randint(enemy.lumis_reward_min, enemy.lumis_reward_max)
        
        base_exp_per_player = total_exp // num_players
        base_lumis_per_player = total_lumis // num_players

        # 2. Get highest drop rate for Party Shared Loot
        highest_party_drop_rate = max([p.total_drop_rate for p in alive_players]) if alive_players else 1.0

        # Initialize log dictionary for each player
        for p in alive_players:
            logs[p.name] = {
                "exp_gained": 0,
                "lumis_gained": 0,
                "items_dropped": [],
                "level_up": False
            }

        party = combat_instance.party

        from apps.quests.services import QuestService

        # 3. Distribute EXP, Lumis, and Items
        for enemy in defeated_enemies:
            # Update quests for defeated enemy
            for player in alive_players:
                QuestService.update_progress(player, 'DEFEAT_ENEMY', enemy_id=enemy.id, count=1)

            # Process Loot Table
            for loot in enemy.loot_tables.all():
                if loot.is_party_shared:
                    # Party Shared Loot
                    if random.random() <= (loot.base_drop_rate * highest_party_drop_rate):
                        qty = random.randint(loot.min_quantity, loot.max_quantity)
                        if party:
                            # Add to Pending Party Loot
                            PendingPartyLoot.objects.create(
                                party=party,
                                item_template=loot.item_template,
                                quantity=qty
                            )
                            # Add a generic log
                            if "party_loot" not in logs:
                                logs["party_loot"] = []
                            logs["party_loot"].append({"name": loot.item_template.name, "qty": qty})
                else:
                    # Personal Loot
                    for player in alive_players:
                        if random.random() <= (loot.base_drop_rate * player.total_drop_rate):
                            qty = random.randint(loot.min_quantity, loot.max_quantity)
                            
                            # Give item to player
                            if loot.item_template.item_type in ['equipment']:
                                # Create separate entries for equipments
                                for _ in range(qty):
                                    InventoryItem.objects.create(
                                        template=loot.item_template,
                                        owner=player,
                                        quantity=1
                                    )
                            else:
                                # Stackable items
                                inventory_item, created = InventoryItem.objects.get_or_create(
                                    template=loot.item_template,
                                    owner=player,
                                    is_destroyed=False,
                                    defaults={'quantity': 0}
                                )
                                inventory_item.quantity += qty
                                inventory_item.save(update_fields=['quantity'])
                            
                            # Trigger Quest Progress for item collection
                            QuestService.update_progress(player, 'COLLECT_ITEM', item_id=loot.item_template.id, count=qty)
                            
                            logs[player.name]["items_dropped"].append({"name": loot.item_template.name, "qty": qty})

        # Add Dungeon specific rewards and logs
        if combat_instance.normal_dungeon:
            dungeon = combat_instance.normal_dungeon
            total_exp += dungeon.exp_reward
            total_lumis += dungeon.lumis_reward
            base_exp_per_player = total_exp // num_players
            base_lumis_per_player = total_lumis // num_players
            
            # Deduct stamina
            for player in alive_players:
                player.update_stamina()
                if player.current_stamina >= dungeon.stamina_cost:
                    player.current_stamina -= dungeon.stamina_cost
                    player.save(update_fields=['current_stamina'])
                else:
                    # Player doesn't have enough stamina, maybe we just don't give them rewards?
                    # Or we let it slide since it should be checked at entry.
                    player.current_stamina = 0
                    player.save(update_fields=['current_stamina'])
                
                # Update quest progress for Normal Dungeon clear
                QuestService.update_progress(player, 'CLEAR_NORMAL_DUNGEON', dungeon_id=dungeon.id)
                    
        elif combat_instance.boss_dungeon:
            dungeon = combat_instance.boss_dungeon
            total_exp += dungeon.exp_reward
            total_lumis += dungeon.lumis_reward
            base_exp_per_player = total_exp // num_players
            base_lumis_per_player = total_lumis // num_players
            
            # Create Clear Logs
            from apps.world.models import DungeonClearLog
            for player in alive_players:
                DungeonClearLog.objects.create(
                    character=player,
                    dungeon=dungeon
                )
                
                # Update quest progress for Boss Dungeon clear
                QuestService.update_progress(player, 'CLEAR_BOSS_DUNGEON', boss_dungeon_id=dungeon.id)

        # Apply EXP and Lumis
        for player in alive_players:
            # Applying character-specific multipliers
            final_exp = int(base_exp_per_player * player.total_exp_rate)
            final_lumis = int(base_lumis_per_player * player.total_drop_rate)

            # Give Lumis
            game_user = player.user
            if game_user:
                game_user.lumis += final_lumis
                game_user.save(update_fields=['lumis'])

            # Give EXP and check Level Up
            old_level = player.level
            player.gain_exp(final_exp)
            
            logs[player.name]["exp_gained"] += final_exp
            logs[player.name]["lumis_gained"] += final_lumis
            logs[player.name]["level_up"] = (player.level > old_level)

        return logs
