from django.db import transaction
from django.db.models import Q

from apps.characters.models import CharacterSkill
from apps.inventory.consumption_service import MaterialConsumptionError, consume_materials
from apps.skilles.models import SkillLevelConfig, SkillTemplate


class SkillService:
    """Owns player skill unlock, catch-up and manual-upgrade rules."""

    @staticmethod
    @transaction.atomic
    def sync_eligible_skills(character):
        """
        Catch a character up through every eligible automatic milestone.

        Processing stops before a material-gated level, so later automatic
        levels cannot skip a required manual upgrade. Calling this repeatedly is
        idempotent. Legacy skills without level configs unlock at template level.
        """
        if not character.pk:
            return []

        ownership = Q(job__isnull=True)
        if character.job_id:
            ownership |= Q(job_id=character.job_id)

        templates = SkillTemplate.objects.filter(
            ownership,
            availability__in=[
                SkillTemplate.Availability.PLAYER,
                SkillTemplate.Availability.BOTH,
            ],
            required_level__lte=character.level,
        ).prefetch_related('level_configs').order_by('id')

        changed_ids = []
        for template in templates:
            owned = CharacterSkill.objects.select_for_update().filter(
                character=character,
                skill_template=template,
            ).first()
            current_level = owned.level if owned else 0
            configs = list(template.level_configs.all())

            if not configs:
                if owned is None:
                    owned = CharacterSkill.objects.create(
                        character=character,
                        skill_template=template,
                        level=1,
                    )
                    changed_ids.append(owned.id)
                continue

            for config in configs:
                next_level = current_level + 1
                if config.skill_level < next_level:
                    continue
                if config.skill_level > next_level:
                    break
                if config.required_char_level > character.level:
                    break
                if config.requires_materials:
                    break

                if owned is None:
                    owned = CharacterSkill.objects.create(
                        character=character,
                        skill_template=template,
                        level=config.skill_level,
                    )
                else:
                    owned.level = config.skill_level
                    owned.save(update_fields=['level'])
                current_level = config.skill_level
                changed_ids.append(owned.id)

        return changed_ids

    @staticmethod
    def auto_sync_skills(character):
        """Backward-compatible name for existing callers."""
        return SkillService.sync_eligible_skills(character)

    @staticmethod
    def manual_upgrade(character, char_skill_id):
        """Upgrade one owned skill through its next material-gated milestone."""
        try:
            with transaction.atomic():
                try:
                    char_skill = CharacterSkill.objects.select_for_update().get(
                        id=char_skill_id,
                        character=character,
                    )
                except CharacterSkill.DoesNotExist:
                    return False, 'Skill not found.'

                next_level = char_skill.level + 1
                try:
                    config = SkillLevelConfig.objects.get(
                        skill=char_skill.skill_template,
                        skill_level=next_level,
                    )
                except SkillLevelConfig.DoesNotExist:
                    return False, f'No upgrade config found for level {next_level}.'

                if character.level < config.required_char_level:
                    return False, (
                        f'Character level {config.required_char_level} required '
                        f'(currently {character.level}).'
                    )
                if not config.requires_materials:
                    return False, 'This upgrade is applied automatically.'

                consume_materials(character, config.required_materials)
                char_skill.level = next_level
                char_skill.save(update_fields=['level'])
                SkillService.sync_eligible_skills(character)
                char_skill.refresh_from_db(fields=['level'])
                return True, f'Skill upgraded; current level is {char_skill.level}.'
        except MaterialConsumptionError as exc:
            return False, exc.message
