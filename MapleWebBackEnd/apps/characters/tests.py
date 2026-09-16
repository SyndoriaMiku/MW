from django.test import TestCase

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
