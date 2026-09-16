from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('items', '0009_auroralinecountconfig_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemtemplate',
            name='icon_key',
            field=models.CharField(
                blank=True,
                help_text='Stable frontend key for the inventory/shop icon.',
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='itemtemplate',
            name='visual_key',
            field=models.CharField(
                blank=True,
                help_text='Stable frontend key for the equipped or in-world visual.',
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
    ]
