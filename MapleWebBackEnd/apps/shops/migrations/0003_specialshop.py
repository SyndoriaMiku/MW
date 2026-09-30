import django.db.models.deletion
from django.db import migrations, models


def move_items_to_a_general_shop(apps, schema_editor):
    """Items that existed before shops did go into one permanent shop."""
    SpecialShop = apps.get_model('shops', 'SpecialShop')
    SpecialShopItem = apps.get_model('shops', 'SpecialShopItem')
    if not SpecialShopItem.objects.filter(shop__isnull=True).exists():
        return
    general = SpecialShop.objects.create(name='General Exchange', description='Permanent exchange shop.')
    SpecialShopItem.objects.filter(shop__isnull=True).update(shop=general)


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0002_shopitem_reset_cycle_alter_shopitem_stock_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpecialShop",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True, help_text="Switch the shop off without deleting it")),
                ("required_level", models.PositiveIntegerField(default=1)),
                ("start_time", models.DateTimeField(blank=True, help_text="Empty = open from now", null=True)),
                ("end_time", models.DateTimeField(blank=True, help_text="Empty = never closes", null=True)),
            ],
            options={
                "verbose_name": "Special Shop",
                "verbose_name_plural": "Special Shops",
                "ordering": ["order", "id"],
            },
        ),
        migrations.AddField(
            model_name="specialshopitem",
            name="shop",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="items", to="shops.specialshop",
            ),
        ),
        migrations.RunPython(move_items_to_a_general_shop, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="specialshopitem",
            name="shop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items", to="shops.specialshop",
            ),
        ),
        migrations.AlterModelOptions(
            name="specialshopitem",
            options={
                "ordering": ["shop", "id"],
                "verbose_name": "Special Shop Item",
                "verbose_name_plural": "Special Shop Items",
            },
        ),
    ]
