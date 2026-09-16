from django.test import TestCase

from .models import ItemTemplate
from .serializers import ItemTemplateSerializer


class ItemTemplateAssetKeyTests(TestCase):
    def test_asset_keys_are_exposed_by_item_api_serializer(self):
        item = ItemTemplate.objects.create(
            name='Copper Bow',
            item_type='weapon',
            weapon_type='bow',
            icon_key='equipment.weapon.copper_bow.icon',
            visual_key='equipment.weapon.copper_bow',
        )

        data = ItemTemplateSerializer(item).data

        self.assertEqual(data['icon_key'], 'equipment.weapon.copper_bow.icon')
        self.assertEqual(data['visual_key'], 'equipment.weapon.copper_bow')
