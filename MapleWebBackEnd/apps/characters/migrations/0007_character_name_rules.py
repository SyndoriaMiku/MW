import unicodedata

import apps.characters.names
from django.db import migrations, models


def fill_name_keys(apps, schema_editor):
    Character = apps.get_model('characters', 'Character')
    for character in Character.objects.only('pk', 'name'):
        # Same as apps.characters.names.name_key, frozen here.
        character.name_key = unicodedata.normalize('NFC', character.name.strip()).casefold()
        character.save(update_fields=['name_key'])


class Migration(migrations.Migration):

    dependencies = [
        ("characters", "0006_final_damage_and_passives"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="character",
            name="unique_character_name_ci",
        ),
        migrations.AlterField(
            model_name="character",
            name="name",
            field=models.CharField(
                help_text="See apps/characters/names.py",
                max_length=20,
                validators=[apps.characters.names.validate_character_name],
            ),
        ),
        migrations.AddField(
            model_name="character",
            name="name_key",
            field=models.CharField(editable=False, max_length=40, null=True),
        ),
        migrations.RunPython(fill_name_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="character",
            name="name_key",
            field=models.CharField(editable=False, max_length=40, unique=True),
        ),
    ]
