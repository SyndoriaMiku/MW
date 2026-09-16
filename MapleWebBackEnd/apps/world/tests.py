from django.test import SimpleTestCase

from .models import EnemyTemplate


class EnemyTemplateDisplayTests(SimpleTestCase):
    def test_admin_choice_uses_enemy_name(self):
        enemy = EnemyTemplate(name='Training Slime')

        self.assertEqual(str(enemy), 'Training Slime')
