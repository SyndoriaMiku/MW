from django.test import TestCase

from apps.classes.models import CharacterClass, Job
from apps.world.models import ExperienceTable

from .models import Character
from .serializers import CharacterSerializer


class CharacterRequiredExpSerializerTests(TestCase):
    def test_returns_required_exp_for_next_level(self):
        ExperienceTable.objects.create(level=1, required_exp=15)
        character = Character.objects.create(name='Level Tester', level=1, current_exp=4)

        data = CharacterSerializer(character).data

        self.assertEqual(data['current_exp'], 4)
        self.assertEqual(data['required_exp'], 15)

    def test_returns_null_when_current_level_has_no_exp_configuration(self):
        character = Character.objects.create(name='Max Level Tester', level=100)

        data = CharacterSerializer(character).data

        self.assertIsNone(data['required_exp'])


class MinimumDamageTests(TestCase):
    def test_damage_below_one_after_rounding_becomes_one(self):
        warrior = CharacterClass.objects.create(name='Warrior', main_stat='str')
        # STR 10 x ATT 5 / 100 = 0.5, which rounds to 0.
        character = Character.objects.create(
            name='Rookie', character_class=warrior,
            job=Job.objects.create(name='Fighter', character_class=warrior),
            base_str=10, base_att=5,
        )

        self.assertEqual(character.total_damage, 1)
        self.assertEqual(
            character.damage_from(str_value=0, agi_value=0, int_value=0, att_value=0), 1
        )

    def test_character_without_a_job_also_deals_at_least_one(self):
        character = Character.objects.create(name='Jobless', base_att=0)

        self.assertEqual(character.total_damage, 1)

    def test_normal_damage_is_unchanged(self):
        warrior = CharacterClass.objects.create(name='Knight', main_stat='str')
        character = Character.objects.create(
            name='Veteran', character_class=warrior,
            job=Job.objects.create(name='Guard', character_class=warrior),
            base_str=30, base_att=50,
        )

        self.assertEqual(character.total_damage, 15)
