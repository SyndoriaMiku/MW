import apps.skilles.validators
import django.core.validators
from django.db import migrations, models


def validate_existing_material_configs(apps, schema_editor):
    SkillLevelConfig = apps.get_model('skilles', 'SkillLevelConfig')
    ItemTemplate = apps.get_model('items', 'ItemTemplate')
    existing_template_ids = set(ItemTemplate.objects.values_list('pk', flat=True))

    for config in SkillLevelConfig.objects.all().iterator():
        materials = config.required_materials
        if not isinstance(materials, list):
            raise RuntimeError(f'SkillLevelConfig {config.pk}: required_materials must be a list.')

        seen = set()
        for index, material in enumerate(materials):
            if not isinstance(material, dict) or set(material) != {'item_template_id', 'quantity'}:
                raise RuntimeError(f'SkillLevelConfig {config.pk}: invalid material at index {index}.')
            template_id = material['item_template_id']
            quantity = material['quantity']
            if (
                isinstance(template_id, bool)
                or not isinstance(template_id, int)
                or template_id <= 0
                or template_id not in existing_template_ids
            ):
                raise RuntimeError(f'SkillLevelConfig {config.pk}: invalid item_template_id at index {index}.')
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
                raise RuntimeError(f'SkillLevelConfig {config.pk}: invalid quantity at index {index}.')
            if template_id in seen:
                raise RuntimeError(f'SkillLevelConfig {config.pk}: duplicate item_template_id={template_id}.')
            seen.add(template_id)


class Migration(migrations.Migration):

    dependencies = [
        ('items', '0009_auroralinecountconfig_and_more'),
        ('skilles', '0003_add_skill_level_config'),
    ]

    operations = [
        migrations.RunPython(validate_existing_material_configs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='skilllevelconfig',
            name='skill_level',
            field=models.IntegerField(
                help_text='Which level of the skill this config applies to. 1 = first unlock.',
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name='skilllevelconfig',
            name='required_char_level',
            field=models.IntegerField(
                help_text='Character must be at or above this level to unlock/upgrade this skill level.',
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name='skilllevelconfig',
            name='required_materials',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'List of materials required for manual upgrade. Empty means auto-upgrade on level-up. '
                    'Format: [{"item_template_id": 1, "quantity": 5}, ...]'
                ),
                validators=[apps.skilles.validators.validate_material_requirements],
            ),
        ),
    ]
