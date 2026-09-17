from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character, CharacterSkill
from apps.characters.skill_service import SkillService
from apps.classes.models import CharacterClass, Job
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser
from apps.world.models import ExperienceTable

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

    def test_level_one_cannot_require_materials(self):
        config = SkillLevelConfig(
            skill=self.skill,
            skill_level=1,
            required_char_level=1,
            required_materials=[{
                'item_template_id': self.material.id,
                'quantity': 1,
            }],
        )

        with self.assertRaises(ValidationError):
            config.full_clean()


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


class SkillLifecycleTests(TestCase):
    def setUp(self):
        self.archer = CharacterClass.objects.create(name='Archer', main_stat='agi')
        self.magician = CharacterClass.objects.create(name='Magician', main_stat='int')
        self.bowman = Job.objects.create(
            name='Bowman', character_class=self.archer, main_stat_weight=1.0
        )
        self.ignis = Job.objects.create(
            name='Ignis Mage', character_class=self.magician, main_stat_weight=1.0
        )

    def test_catch_up_stops_at_material_then_continues_after_manual_upgrade(self):
        material = ItemTemplate.objects.create(name='Skill Book', item_type='etc')
        skill = SkillTemplate.objects.create(name='Arrow Mastery', job=self.bowman)
        SkillLevelConfig.objects.create(
            skill=skill, skill_level=1, required_char_level=1
        )
        SkillLevelConfig.objects.create(
            skill=skill,
            skill_level=2,
            required_char_level=2,
            required_materials=[{'item_template_id': material.id, 'quantity': 1}],
        )
        SkillLevelConfig.objects.create(
            skill=skill, skill_level=3, required_char_level=3
        )
        character = Character.objects.create(
            name='High Archer', character_class=self.archer, job=self.bowman, level=10
        )

        SkillService.sync_eligible_skills(character)
        owned = CharacterSkill.objects.get(character=character, skill_template=skill)
        self.assertEqual(owned.level, 1)

        InventoryItem.objects.create(owner=character, template=material, quantity=1)
        success, _ = SkillService.manual_upgrade(character, owned.id)

        self.assertTrue(success)
        owned.refresh_from_db()
        self.assertEqual(owned.level, 3)

    def test_sync_is_idempotent_and_excludes_other_job_and_enemy_skills(self):
        bow_skill = SkillTemplate.objects.create(name='Bow Shot', job=self.bowman)
        SkillTemplate.objects.create(name='Fire Bolt', job=self.ignis)
        SkillTemplate.objects.create(
            name='Monster Bite',
            availability=SkillTemplate.Availability.ENEMY,
        )
        global_skill = SkillTemplate.objects.create(name='First Aid')
        character = Character.objects.create(
            name='Archer', character_class=self.archer, job=self.bowman
        )

        SkillService.sync_eligible_skills(character)
        SkillService.sync_eligible_skills(character)

        owned_ids = set(character.skills.values_list('skill_template_id', flat=True))
        self.assertEqual(owned_ids, {bow_skill.id, global_skill.id})
        self.assertEqual(character.skills.count(), 2)

    def test_management_command_catches_up_existing_character(self):
        skill = SkillTemplate.objects.create(name='Legacy Bow Skill', job=self.bowman)
        character = Character.objects.create(
            name='Existing Archer', character_class=self.archer, job=self.bowman
        )
        output = StringIO()

        call_command('sync_character_skills', character_id=character.id, stdout=output)

        self.assertTrue(
            CharacterSkill.objects.filter(character=character, skill_template=skill).exists()
        )
        self.assertIn('Synced 1 character', output.getvalue())

    def test_multi_level_gain_catches_up_all_automatic_skill_levels(self):
        skill = SkillTemplate.objects.create(name='Rapid Shot', job=self.bowman)
        for level in range(1, 4):
            SkillLevelConfig.objects.create(
                skill=skill,
                skill_level=level,
                required_char_level=level,
            )
        ExperienceTable.objects.create(level=1, required_exp=1)
        ExperienceTable.objects.create(level=2, required_exp=1)
        character = Character.objects.create(
            name='Leveling Archer', character_class=self.archer, job=self.bowman
        )
        SkillService.sync_eligible_skills(character)

        character.gain_exp(2)

        owned = CharacterSkill.objects.get(character=character, skill_template=skill)
        self.assertEqual(character.level, 3)
        self.assertEqual(owned.level, 3)


class CharacterSkillAPITests(APITestCase):
    def setUp(self):
        self.archer = CharacterClass.objects.create(name='Archer', main_stat='agi')
        self.bowman = Job.objects.create(
            name='Bowman', character_class=self.archer, main_stat_weight=1.0
        )
        self.skill = SkillTemplate.objects.create(name='Basic Bow Attack', job=self.bowman)
        SkillLevelConfig.objects.create(
            skill=self.skill, skill_level=1, required_char_level=1
        )
        self.user = GameUser.objects.create_user(
            username='skill-api-user', email='skill-api@example.com', password='test-pass-123'
        )
        self.client.force_authenticate(self.user)

    def test_character_creation_infers_class_and_grants_initial_skill(self):
        response = self.client.post(
            reverse('character-create'),
            {'name': 'New Bowman', 'job': self.bowman.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['character_class'], self.archer.id)
        self.assertEqual(response.data['job'], self.bowman.id)
        self.assertEqual(len(response.data['skills']), 1)
        self.assertEqual(
            response.data['skills'][0]['skill_template_id'], self.skill.id
        )

    def test_owned_skill_route_returns_explicit_ids(self):
        character = Character.objects.create(
            name='API Archer', character_class=self.archer, job=self.bowman
        )
        self.user.character = character
        self.user.save(update_fields=['character'])
        owned = CharacterSkill.objects.create(
            character=character, skill_template=self.skill
        )

        response = self.client.get(reverse('my-skills'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['character_skill_id'], owned.id)
        self.assertEqual(response.data[0]['skill_template_id'], self.skill.id)
        self.assertEqual(response.data[0]['skill_id'], self.skill.id)

    def test_character_creation_rejects_job_from_another_class(self):
        magician = CharacterClass.objects.create(name='Magician', main_stat='int')

        response = self.client.post(
            reverse('character-create'),
            {
                'name': 'Invalid Bowman',
                'character_class': magician.id,
                'job': self.bowman.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('job', response.data)

    def test_owned_skill_route_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse('my-skills'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_upgrade_another_characters_skill(self):
        own_character = Character.objects.create(
            name='Own Archer', character_class=self.archer, job=self.bowman
        )
        other_character = Character.objects.create(
            name='Other Archer', character_class=self.archer, job=self.bowman
        )
        self.user.character = own_character
        self.user.save(update_fields=['character'])
        other_skill = CharacterSkill.objects.create(
            character=other_character,
            skill_template=self.skill,
        )

        response = self.client.post(reverse('upgrade-skill', args=[other_skill.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Skill not found.')
