from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.services import BattleService
from apps.characters.models import Character, RateEvent
from apps.party.models import Party, PartyMember
from apps.world.models import EnemyTemplate

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


class SessionBootstrapTests(APITestCase):
    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='bootstrap', email='bootstrap@example.com', password='test-pass-123'
        )
        self.url = reverse('session-bootstrap')

    def test_bootstrap_endpoint_is_routed(self):
        self.assertEqual(self.url, '/api/session/bootstrap/')

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_character(self):
        self.client.force_authenticate(self.user)

        data = self.client.get(self.url).data

        self.assertEqual(data['profile']['username'], 'bootstrap')
        self.assertIsNone(data['character'])
        self.assertIsNone(data['party'])
        self.assertIsNone(data['active_battle'])
        self.assertTrue(data['feature_flags']['action_idempotency'])
        self.assertEqual(data['battle_turn_timeout_seconds'], settings.BATTLE_TURN_TIMEOUT_SECONDS)

    def test_character_in_party_and_active_battle(self):
        character = Character.objects.create(name='Bootstrapper')
        self.user.character = character
        self.user.save(update_fields=['character'])
        party = Party.objects.create(name='Boot Party', leader=character, max_size=1)
        PartyMember.objects.create(party=party, character=character, position=1)
        enemy = EnemyTemplate.objects.create(
            name='Boot Slime', level=1, base_hp=10, base_mp=0, base_att=1,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        combat = BattleService.create_combat_instance(party, [enemy])
        BattleService.start_combat(combat)
        self.client.force_authenticate(self.user)

        data = self.client.get(self.url).data

        self.assertEqual(data['character']['id'], character.id)
        self.assertEqual(data['party']['id'], party.id)
        self.assertEqual(data['active_battle']['id'], combat.id)
        self.assertEqual(data['active_battle']['version'], 0)

    def test_lists_running_rate_events(self):
        RateEvent.objects.create(name='Double EXP', is_active=True, exp_rate_bonus=100)
        RateEvent.objects.create(name='Switched off', is_active=False, exp_rate_bonus=100)
        self.client.force_authenticate(self.user)

        data = self.client.get(self.url).data

        self.assertEqual([event['name'] for event in data['rate_events']], ['Double EXP'])
        self.assertEqual(data['rate_events'][0]['exp_rate_bonus'], 100)


class DefaultPermissionTests(APITestCase):
    def test_endpoints_require_authentication_unless_declared_public(self):
        self.assertEqual(self.client.get('/api/market/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get('/api/inventory/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_public_catalog_and_registration_stay_anonymous(self):
        self.assertEqual(self.client.get('/api/classes/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/skills/').status_code, status.HTTP_200_OK)
        response = self.client.post(
            reverse('register'),
            {'username': 'anon-register', 'email': 'anon@example.com', 'password': 'Sturdy-pass-4821'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class RegistrationPasswordTests(APITestCase):
    def register(self, password, username='new-player'):
        return self.client.post(
            reverse('register'),
            {'username': username, 'email': f'{username}@example.com', 'password': password},
            format='json',
        )

    def test_weak_passwords_are_rejected(self):
        for password in ('1', 'password', '12345678', 'new-player1'):
            with self.subTest(password=password):
                response = self.register(password)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('password', response.data)
        self.assertFalse(GameUser.objects.filter(username='new-player').exists())

    def test_password_is_hashed_and_never_returned(self):
        response = self.register('Sturdy-pass-4821')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        self.assertTrue(GameUser.objects.get(username='new-player').check_password('Sturdy-pass-4821'))
