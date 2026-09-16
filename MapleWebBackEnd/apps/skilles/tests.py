from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.characters.models import Character, CharacterSkill
from apps.characters.skill_service import SkillService
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate

from .models import SkillLevelConfig, SkillTemplate


class SkillMaterialValidationTests(TestCase):
    def setUp(self):
        self.skill = SkillTemplate.objects.create(name='Validation Skill')
        self.material = ItemTemplate.objects.create(name='Valid Material', item_type='etc')

    def assert_invalid_materials(self, materials):
        config = SkillLevelConfig(
            skill=self.skill,
            skill_level=2,
            required_char_level=2,
            required_materials=materials,
        )
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_rejects_invalid_material_shapes(self):
        invalid_values = [
            {'item_template_id': self.material.id, 'quantity': 1},
            [{'item_template_id': self.material.id}],
            [{'item_template_id': self.material.id, 'quantity': 0}],
            [{'item_template_id': True, 'quantity': 1}],
            [
                {'item_template_id': self.material.id, 'quantity': 1},
                {'item_template_id': self.material.id, 'quantity': 1},
            ],
            [{'item_template_id': 999999, 'quantity': 1}],
        ]
        for materials in invalid_values:
            with self.subTest(materials=materials):
                self.assert_invalid_materials(materials)


class ManualSkillUpgradeAtomicityTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='SkillTester', level=10)
        self.skill = SkillTemplate.objects.create(name='Upgrade Skill')
        self.character_skill = CharacterSkill.objects.create(
            character=self.character, skill_template=self.skill, level=1
        )
        self.material_a = ItemTemplate.objects.create(name='Skill Material A', item_type='etc')
        self.material_b = ItemTemplate.objects.create(name='Skill Material B', item_type='etc')
        SkillLevelConfig.objects.create(
            skill=self.skill,
            skill_level=2,
            required_char_level=2,
            required_materials=[
                {'item_template_id': self.material_a.id, 'quantity': 3},
                {'item_template_id': self.material_b.id, 'quantity': 2},
            ],
        )

    def test_failed_upgrade_keeps_all_materials_and_skill_level(self):
        material_a_stack = InventoryItem.objects.create(
            owner=self.character, template=self.material_a, quantity=3
        )

        success, _ = SkillService.manual_upgrade(self.character, self.character_skill.id)

        self.assertFalse(success)
        material_a_stack.refresh_from_db()
        self.character_skill.refresh_from_db()
        self.assertEqual(material_a_stack.quantity, 3)
        self.assertEqual(self.character_skill.level, 1)

    def test_successful_upgrade_consumes_all_materials(self):
        InventoryItem.objects.create(owner=self.character, template=self.material_a, quantity=3)
        InventoryItem.objects.create(owner=self.character, template=self.material_b, quantity=2)

        success, _ = SkillService.manual_upgrade(self.character, self.character_skill.id)

        self.assertTrue(success)
        self.character_skill.refresh_from_db()
        self.assertEqual(self.character_skill.level, 2)
        self.assertFalse(InventoryItem.objects.filter(owner=self.character).exists())
