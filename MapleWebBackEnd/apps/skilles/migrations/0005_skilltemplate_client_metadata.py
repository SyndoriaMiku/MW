from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('skilles', '0004_validate_skill_materials'),
    ]

    operations = [
        migrations.AddField(
            model_name='skilltemplate',
            name='availability',
            field=models.CharField(
                choices=[
                    ('PLAYER', 'Player'),
                    ('ENEMY', 'Enemy'),
                    ('BOTH', 'Player and Enemy'),
                ],
                default='PLAYER',
                help_text='Which combatant types may own and use this skill.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='skilltemplate',
            name='icon_key',
            field=models.CharField(
                blank=True,
                help_text='Stable frontend key for the skill icon.',
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='skilltemplate',
            name='visual_key',
            field=models.CharField(
                blank=True,
                help_text='Stable frontend key for the skill animation or VFX.',
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
    ]
