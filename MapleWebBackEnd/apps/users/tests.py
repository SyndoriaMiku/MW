from django.test import TestCase

from apps.characters.models import Character

from .models import GameUser


class CharacterDeletionTests(TestCase):
    def test_deleting_character_keeps_the_account(self):
        user = GameUser.objects.create_user(
            username='keep-me', email='keep-me@example.com', password='test-pass-123'
        )
        user.character = Character.objects.create(name='Doomed')
        user.save(update_fields=['character'])

        user.character.delete()

        user.refresh_from_db()
        self.assertIsNone(user.character)
