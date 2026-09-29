from django.utils import timezone
from django.db import transaction
from django.db.models import F
from apps.reset_cycles import is_current_period

from .models import QuestTemplate, QuestReward, CharacterQuest, CharacterQuestObjective

class QuestService:
    @staticmethod
    def get_active_quests(character):
        """
        Retrieves the character's quests.
        Provisions every quest the character is eligible for (level reached and
        every prerequisite quest claimed) and lazily resets daily/weekly quests.
        """
        now = timezone.now()
        owned = {cq.quest_id: cq for cq in CharacterQuest.objects.filter(character=character)}
        claimed_ids = {
            quest_id for quest_id, cq in owned.items()
            if cq.status == CharacterQuest.Status.CLAIMED
        }

        templates = QuestTemplate.objects.prefetch_related('prerequisite_quests', 'objectives')
        for template in templates:
            cq = owned.get(template.id)
            if cq is None:
                eligible = template.required_level <= character.level and all(
                    prerequisite.id in claimed_ids
                    for prerequisite in template.prerequisite_quests.all()
                )
                if not eligible:
                    continue
                cq, _ = CharacterQuest.objects.get_or_create(
                    character=character,
                    quest=template,
                    defaults={'last_reset_at': now, 'status': CharacterQuest.Status.IN_PROGRESS}
                )
            elif (
                template.quest_type != QuestTemplate.QuestType.ONCE
                and not is_current_period(cq.last_reset_at, template.quest_type, now)
            ):
                # Reset once the quest's calendar period has rolled over.
                cq.status = CharacterQuest.Status.IN_PROGRESS
                cq.last_reset_at = now
                cq.completed_at = None
                cq.save()

                # Reset objectives
                for obj_progress in cq.objective_progress.all():
                    obj_progress.current_count = 0
                    obj_progress.is_completed = False
                    obj_progress.save()

            objectives = template.objectives.all()
            if objectives:
                # Ensure objectives exist
                if not cq.objective_progress.exists():
                    QuestService.initialize_objectives(cq)
            elif cq.status == CharacterQuest.Status.IN_PROGRESS:
                # Nothing to do (e.g. a story hand-off): ready to claim.
                cq.status = CharacterQuest.Status.COMPLETED
                cq.completed_at = now
                cq.save(update_fields=['status', 'completed_at'])

        return CharacterQuest.objects.filter(character=character).order_by('-started_at')

    @staticmethod
    def initialize_objectives(character_quest):
        """Initializes progress tracking for all objectives of a new or reset quest."""
        objectives = character_quest.quest.objectives.all()
        for obj in objectives:
            CharacterQuestObjective.objects.get_or_create(
                character_quest=character_quest,
                objective=obj
            )

    @staticmethod
    def check_quest_completion(character_quest):
        """Checks if all objectives are completed and updates the quest status."""
        if character_quest.status != CharacterQuest.Status.IN_PROGRESS:
            return False

        all_completed = True
        for obj_progress in character_quest.objective_progress.all():
            if not obj_progress.is_completed:
                all_completed = False
                break
        
        if all_completed and character_quest.objective_progress.exists():
            character_quest.status = CharacterQuest.Status.COMPLETED
            character_quest.completed_at = timezone.now()
            character_quest.save()
            return True
        return False

    @staticmethod
    def update_progress(character, action_type, **kwargs):
        """
        Updates quest progress based on an action.
        action_type can be: 'DEFEAT_ENEMY', 'COLLECT_ITEM', 'CLEAR_NORMAL_DUNGEON', 'CLEAR_BOSS_DUNGEON'
        """
        # (S2 fix) get_active_quests is now called explicitly before battles, not per-action here.
        active_quests = CharacterQuest.objects.filter(
            character=character, 
            status=CharacterQuest.Status.IN_PROGRESS
        )
        
        for cq in active_quests:
            progresses = cq.objective_progress.filter(is_completed=False)
            quest_updated = False
            
            for p in progresses:
                obj = p.objective
                obj_updated = False
                target_count = 1
                
                if action_type == 'DEFEAT_ENEMY':
                    enemy_id = kwargs.get('enemy_id')
                    count = kwargs.get('count', 1)
                    if obj.defeat_count > 0:
                        if obj.enemy_to_defeat is None or obj.enemy_to_defeat.id == enemy_id:
                            p.current_count += count
                            target_count = obj.defeat_count
                            obj_updated = True
                
                elif action_type == 'COLLECT_ITEM':
                    item_id = kwargs.get('item_id')
                    count = kwargs.get('count', 1)
                    if obj.collect_count > 0 and obj.item_to_collect and obj.item_to_collect.id == item_id:
                        p.current_count += count
                        target_count = obj.collect_count
                        obj_updated = True
                        
                elif action_type == 'CLEAR_NORMAL_DUNGEON':
                    dungeon_id = kwargs.get('dungeon_id')
                    if obj.clear_count > 0:
                        if obj.dungeon_to_clear is None or obj.dungeon_to_clear.id == dungeon_id:
                            p.current_count += 1
                            target_count = obj.clear_count
                            obj_updated = True
                        
                elif action_type == 'CLEAR_BOSS_DUNGEON':
                    boss_dungeon_id = kwargs.get('boss_dungeon_id')
                    if obj.boss_clear_count > 0:
                        if obj.boss_dungeon_to_clear is None or obj.boss_dungeon_to_clear.id == boss_dungeon_id:
                            p.current_count += 1
                            target_count = obj.boss_clear_count
                            obj_updated = True

                # Cap current_count and check completion
                if obj_updated:
                    if p.current_count >= target_count:
                        p.current_count = target_count
                        p.is_completed = True
                    p.save(update_fields=['current_count', 'is_completed'])
                    quest_updated = True
            
            if quest_updated:
                QuestService.check_quest_completion(cq)

    @staticmethod
    @transaction.atomic
    def claim_reward(character, quest_id):
        """
        Claims the reward for a completed quest.
        Distributes EXP, Lumis, and Item rewards to the character.
        Returns a dict with success status and details.
        """
        try:
            # (RC-3 fix) Lock quest row to prevent double-claim
            cq = CharacterQuest.objects.select_for_update().select_related('quest').get(
                character=character, quest_id=quest_id
            )
        except CharacterQuest.DoesNotExist:
            return {"success": False, "message": "Quest not found for this character."}

        if cq.status != CharacterQuest.Status.COMPLETED:
            if cq.status == CharacterQuest.Status.CLAIMED:
                return {"success": False, "message": "Rewards already claimed."}
            return {"success": False, "message": "Quest is not yet completed."}

        template = cq.quest
        rewards_log = {"exp": 0, "lumis": 0, "items": []}

        # Grant EXP
        if template.exp_reward > 0:
            character.gain_exp(template.exp_reward)
            rewards_log["exp"] = template.exp_reward

        # Grant Lumis (RC-4 fix: atomic F() increment)
        if template.lumis_reward > 0:
            from apps.users.models import GameUser
            GameUser.objects.filter(pk=character.user.pk).update(
                lumis=F('lumis') + template.lumis_reward
            )
            rewards_log["lumis"] = template.lumis_reward

        # Grant Item Rewards
        from apps.inventory.grant_service import grant_item
        for reward in template.rewards.select_related('item_template').all():
            item_template = reward.item_template
            qty = reward.quantity
            if qty > 0:
                grant_item(character, item_template, qty)

            rewards_log["items"].append({
                "name": item_template.name,
                "quantity": qty
            })

        # Mark quest as claimed
        cq.status = CharacterQuest.Status.CLAIMED
        cq.save(update_fields=['status'])

        return {
            "success": True,
            "message": "Rewards claimed successfully!",
            "rewards": rewards_log
        }
