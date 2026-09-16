from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battles', '0003_activeeffect_remaining_shield_points'),
    ]

    operations = [
        migrations.AddField(
            model_name='combatinstance',
            name='stamina_charged',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='combatinstance',
            name='stamina_cost_on_victory',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
