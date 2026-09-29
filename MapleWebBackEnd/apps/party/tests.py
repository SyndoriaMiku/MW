from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.characters.models import Character
from apps.users.models import GameUser


class MalformedPartyInputTests(APITestCase):
    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='party-bad-input', email='party-bad@example.com', password='test-pass-123'
        )
        self.user.character = Character.objects.create(name='PartyBadInput')
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

    def test_distribute_loot_rejects_non_integer_loot_id(self):
        response = self.client.post(
            reverse('party-distribute-loot'),
            {'loot_id': 'abc', 'character_id': self.user.character.id}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_string_party_name_is_accepted_as_text(self):
        response = self.client.post(reverse('party-create-party'), {'name': 123}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], '123')
