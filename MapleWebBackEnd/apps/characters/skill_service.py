from django.db import transaction
from apps.skilles.models import SkillLevelConfig
from apps.characters.models import CharacterSkill


class SkillService:
    """
    Manages skill unlocking and upgrading for characters.

    Auto-unlock flow (triggered by _level_up):
      1. Query all SkillLevelConfigs for this character's job (or job=null)
         where required_char_level == character.level AND required_materials is empty.
      2. For each config at skill_level == 1 -> grant the skill if not already owned.
      3. For each config at skill_level > 1  -> upgrade if current level is exactly one below.

    Manual upgrade flow (future, for material-based configs):
      Called via POST /api/characters/my/skills/{id}/upgrade/
    """

    @staticmethod
    @transaction.atomic
    def auto_sync_skills(character):
        """
        Called automatically inside Character._level_up().
        Scans all SkillLevelConfigs that:
          - belong to the character's job (or are job-agnostic / job=null)
          - have required_char_level == character.level  (exact match)
          - have no required_materials                   (auto-upgrade only)
        Then grants or upgrades CharacterSkills accordingly.
        """
        job_configs = SkillLevelConfig.objects.filter(
            required_char_level=character.level,
            required_materials=[],
            skill__job=character.job,
        ).select_related('skill')

        global_configs = SkillLevelConfig.objects.filter(
            required_char_level=character.level,
            required_materials=[],
            skill__job__isnull=True,
        ).select_related('skill')

        for config in list(job_configs) + list(global_configs):
            if config.skill_level == 1:
                CharacterSkill.objects.get_or_create(
                    character=character,
                    skill_template=config.skill,
                    defaults={'level': 1}
                )
            else:
                CharacterSkill.objects.filter(
                    character=character,
                    skill_template=config.skill,
                    level=config.skill_level - 1,
                ).update(level=config.skill_level)

    @staticmethod
    @transaction.atomic
    def manual_upgrade(character, char_skill_id):
        """
        Future: Material-based skill upgrade triggered manually by the player.
        Returns (success: bool, message: str).
        """
        from apps.inventory.models import InventoryItem

        try:
            char_skill = CharacterSkill.objects.select_for_update().get(
                id=char_skill_id, character=character
            )
        except CharacterSkill.DoesNotExist:
            return False, "Skill not found."

        next_level = char_skill.level + 1
        try:
            config = SkillLevelConfig.objects.get(
                skill=char_skill.skill_template,
                skill_level=next_level,
            )
        except SkillLevelConfig.DoesNotExist:
            return False, f"No upgrade config found for level {next_level}."

        if character.level < config.required_char_level:
            return False, (
                f"Character level {config.required_char_level} required "
                f"(currently {character.level})."
            )

        if not config.required_materials:
            return False, "This upgrade is applied automatically on level-up."

        for mat in config.required_materials:
            item_template_id = mat.get('item_template_id')
            qty_needed = mat.get('quantity', 1)

            inv_items = InventoryItem.objects.select_for_update().filter(
                owner=character,
                template_id=item_template_id,
                is_destroyed=False,
            ).order_by('quantity')

            total_available = sum(i.quantity for i in inv_items)
            if total_available < qty_needed:
                return False, f"Not enough materials (item_template_id={item_template_id})."

            remaining = qty_needed
            for inv_item in inv_items:
                if remaining <= 0:
                    break
                if inv_item.quantity <= remaining:
                    remaining -= inv_item.quantity
                    inv_item.delete()
                else:
                    inv_item.quantity -= remaining
                    inv_item.save(update_fields=['quantity'])
                    remaining = 0

        char_skill.level = next_level
        char_skill.save(update_fields=['level'])
        return True, f"Skill upgraded to level {next_level}."
