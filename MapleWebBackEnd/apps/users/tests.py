from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.services import BattleService
from apps.characters.models import Character, RateEvent
from apps.party.models import Party, PartyMember
from apps.world.models import EnemyTemplate

from .models import GameUser, NovaTransaction
from .nova_service import NovaError, change_nova


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


@override_settings(
    LOGIN_FAILURE_LIMIT_PER_USER=3,
    LOGIN_FAILURE_LIMIT_PER_IP=5,
    LOGIN_FAILURE_WINDOW_SECONDS=900,
)
class LoginFailureLimitTests(APITestCase):
    """Wrong passwords are limited per account and per IP; correct logins are not counted."""

    def setUp(self):
        cache.clear()
        for name in ('victim', 'other'):
            GameUser.objects.create_user(
                username=name, email=f'{name}@example.com', password='right-pass-123'
            )

    def login(self, username='victim', password='wrong-pass', ip='10.0.0.1'):
        return self.client.post(
            reverse('token_obtain_pair'), {'username': username, 'password': password},
            format='json', REMOTE_ADDR=ip,
        )

    def test_account_is_locked_after_too_many_wrong_passwords(self):
        for _ in range(3):
            self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)

        blocked = self.login(password='right-pass-123')

        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', blocked)
        # The lock is per account: another account on the same IP still works.
        self.assertEqual(self.login('other', 'right-pass-123').status_code, status.HTTP_200_OK)

    def test_account_lock_holds_across_ips(self):
        for index in range(3):
            self.login(ip=f'10.0.0.{index + 1}')

        self.assertEqual(
            self.login(password='right-pass-123', ip='10.0.0.99').status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_correct_login_clears_the_account_counter(self):
        self.login()
        self.login()
        self.assertEqual(self.login(password='right-pass-123').status_code, status.HTTP_200_OK)

        self.login()
        self.login()

        self.assertEqual(self.login(password='right-pass-123').status_code, status.HTTP_200_OK)

    def test_ip_is_blocked_after_too_many_failures_on_any_accounts(self):
        for index in range(5):
            self.login(username=f'guess-{index}')

        blocked = self.login('other', 'right-pass-123')

        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            self.login('other', 'right-pass-123', ip='10.0.0.2').status_code, status.HTTP_200_OK,
        )

    def test_forged_forwarded_for_header_does_not_dodge_the_ip_limit(self):
        # Without a trusted proxy, X-Forwarded-For is whatever the client typed.
        for index in range(5):
            self.client.post(
                reverse('token_obtain_pair'), {'username': f'guess-{index}', 'password': 'wrong-pass'},
                format='json', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR=f'1.2.3.{index}',
            )

        blocked = self.client.post(
            reverse('token_obtain_pair'), {'username': 'other', 'password': 'right-pass-123'},
            format='json', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='9.9.9.9',
        )

        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1})
    def test_behind_a_proxy_the_forwarded_client_ip_is_used(self):
        for index in range(5):
            self.client.post(
                reverse('token_obtain_pair'), {'username': f'guess-{index}', 'password': 'wrong-pass'},
                format='json', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='1.2.3.4',
            )

        other_client = self.client.post(
            reverse('token_obtain_pair'), {'username': 'other', 'password': 'right-pass-123'},
            format='json', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='5.6.7.8',
        )

        self.assertEqual(other_client.status_code, status.HTTP_200_OK)

    def test_lock_ends_when_the_window_passes(self):
        start = 1_000_000.0
        with mock.patch('apps.users.login_limits.time.time', return_value=start):
            for _ in range(3):
                self.login()
            self.assertEqual(
                self.login(password='right-pass-123').status_code, status.HTTP_429_TOO_MANY_REQUESTS,
            )

        with mock.patch('apps.users.login_limits.time.time', return_value=start + 901):
            self.assertEqual(self.login(password='right-pass-123').status_code, status.HTTP_200_OK)


class NovaLedgerTests(APITestCase):
    """Nova only changes through the ledger, which always matches the balance."""

    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='donor', email='donor@example.com', password='test-pass-123'
        )
        self.admin = GameUser.objects.create_superuser(
            username='boss', email='boss@example.com', password='test-pass-123'
        )

    def nova(self):
        return GameUser.objects.get(pk=self.user.pk).nova

    def test_donation_credits_nova_and_is_recorded(self):
        entry = change_nova(
            self.user, 500, NovaTransaction.Kind.DONATION,
            reference='kofi-001', note='Thanks!', created_by=self.admin,
        )

        self.assertEqual(self.nova(), 500)
        self.assertEqual(
            (entry.amount, entry.balance_after, entry.reference, entry.created_by),
            (500, 500, 'kofi-001', self.admin),
        )

    def test_a_donation_reference_is_credited_once(self):
        change_nova(self.user, 500, NovaTransaction.Kind.DONATION, reference='kofi-001')

        with self.assertRaises(NovaError):
            change_nova(self.user, 500, NovaTransaction.Kind.DONATION, reference='kofi-001')
        self.assertEqual(self.nova(), 500)

    def test_invalid_changes_are_refused(self):
        change_nova(self.user, 100, NovaTransaction.Kind.DONATION)

        for amount, kind in [
            (0, NovaTransaction.Kind.ADJUSTMENT),
            (-5, NovaTransaction.Kind.DONATION),
            (-101, NovaTransaction.Kind.ADJUSTMENT),
        ]:
            with self.subTest(amount=amount, kind=kind), self.assertRaises(NovaError):
                change_nova(self.user, amount, kind)
        self.assertEqual(self.nova(), 100)
        self.assertEqual(NovaTransaction.objects.count(), 1)

    def test_admin_adds_a_donation_through_the_ledger(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin:users_novatransaction_add'), {
            'user': self.user.pk, 'kind': 'donation', 'amount': 300,
            'reference': 'kofi-002', 'note': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.nova(), 300)
        entry = NovaTransaction.objects.get()
        self.assertEqual((entry.balance_after, entry.created_by), (300, self.admin))

    def test_admin_form_refuses_taking_more_than_the_balance(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin:users_novatransaction_add'), {
            'user': self.user.pk, 'kind': 'adjustment', 'amount': -1, 'reference': '', 'note': '',
        })

        self.assertEqual(response.status_code, 200)  # form redisplayed with an error
        self.assertFalse(NovaTransaction.objects.exists())

    def test_nova_is_read_only_on_the_user_admin_page(self):
        from .admin import GameUserAdmin

        self.assertIn('nova', GameUserAdmin.readonly_fields)

    def test_player_sees_only_their_own_history_newest_first(self):
        change_nova(self.user, 100, NovaTransaction.Kind.DONATION, reference='a')
        change_nova(self.user, -40, NovaTransaction.Kind.ADJUSTMENT)
        change_nova(self.admin, 999, NovaTransaction.Kind.DONATION, reference='b')
        self.client.force_authenticate(self.user)

        data = self.client.get(reverse('nova-history')).data

        self.assertEqual(
            [(row['kind'], row['amount'], row['balance_after']) for row in data['results']],
            [('adjustment', -40, 60), ('donation', 100, 100)],
        )
        self.assertNotIn('created_by', data['results'][0])


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
        cache.clear()  # registrations are throttled per IP
        self.assertEqual(self.client.get('/api/classes/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/skills/').status_code, status.HTTP_200_OK)
        response = self.client.post(
            reverse('register'),
            {'username': 'anon-register', 'email': 'anon@example.com', 'password': 'Sturdy-pass-4821'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


@override_settings(REST_FRAMEWORK={
    **settings.REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {**settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'register': '2/hour'},
})
class RegistrationThrottleTests(APITestCase):
    """Sign-ups are limited per IP so bots cannot mass-create accounts."""

    def setUp(self):
        cache.clear()

    def register(self, username, ip='10.0.0.1', password='Sturdy-pass-4821'):
        return self.client.post(
            reverse('register'),
            {'username': username, 'email': f'{username}@example.com', 'password': password},
            format='json', REMOTE_ADDR=ip,
        )

    def test_too_many_sign_ups_from_one_ip_are_refused(self):
        self.assertEqual(self.register('first').status_code, status.HTTP_201_CREATED)
        # Failed attempts count too.
        self.assertEqual(self.register('second', password='1').status_code, status.HTTP_400_BAD_REQUEST)

        blocked = self.register('third')

        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', blocked)
        self.assertFalse(GameUser.objects.filter(username='third').exists())
        self.assertEqual(self.register('third', ip='10.0.0.2').status_code, status.HTTP_201_CREATED)


@override_settings(LOGIN_FAILURE_LIMIT_PER_USER=3)
class SessionTests(APITestCase):
    """Changing the password or logging out everywhere ends every session at once."""

    def setUp(self):
        cache.clear()
        self.user = GameUser.objects.create_user(
            username='player', email='player@example.com', password='Old-pass-4821'
        )

    def login(self, password='Old-pass-4821'):
        return self.client.post(
            reverse('token_obtain_pair'), {'username': 'player', 'password': password}, format='json',
        )

    def get_profile(self, access):
        return self.client.get(reverse('profile'), HTTP_AUTHORIZATION=f'Bearer {access}')

    def refresh(self, refresh):
        return self.client.post(reverse('token_refresh'), {'refresh': refresh}, format='json')

    def change_password(self, access, old='Old-pass-4821', new='New-pass-9137'):
        return self.client.post(
            reverse('password-change'), {'old_password': old, 'new_password': new},
            format='json', HTTP_AUTHORIZATION=f'Bearer {access}',
        )

    def test_change_password_ends_other_sessions_and_keeps_this_one(self):
        phone = self.login().data
        laptop = self.login().data

        response = self.change_password(laptop['access'])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for old in (phone, laptop):
            self.assertEqual(self.get_profile(old['access']).status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(self.refresh(old['refresh']).status_code, status.HTTP_401_UNAUTHORIZED)
        # The device that changed the password gets fresh tokens.
        self.assertEqual(self.get_profile(response.data['access']).status_code, status.HTTP_200_OK)
        self.assertEqual(self.refresh(response.data['refresh']).status_code, status.HTTP_200_OK)
        self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.login('New-pass-9137').status_code, status.HTTP_200_OK)

    def test_wrong_old_password_is_refused_and_counts_as_a_failed_login(self):
        access = self.login().data['access']

        response = self.change_password(access, old='not-my-password')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)
        self.assertTrue(GameUser.objects.get(pk=self.user.pk).check_password('Old-pass-4821'))
        # A stolen access token must not allow guessing the password.
        self.change_password(access, old='still-wrong')
        self.change_password(access, old='wrong-again')
        self.assertEqual(
            self.change_password(access).status_code, status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_weak_new_password_is_refused(self):
        access = self.login().data['access']

        response = self.change_password(access, new='12345678')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
        self.assertEqual(self.get_profile(access).status_code, status.HTTP_200_OK)

    def test_logout_all_ends_every_session(self):
        phone = self.login().data
        laptop = self.login().data

        response = self.client.post(reverse('logout-all'), HTTP_AUTHORIZATION=f'Bearer {laptop["access"]}')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        for old in (phone, laptop):
            self.assertEqual(self.get_profile(old['access']).status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(self.refresh(old['refresh']).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_refreshed_tokens_end_with_the_session(self):
        refreshed = self.refresh(self.login().data['refresh']).data
        self.assertEqual(self.get_profile(refreshed['access']).status_code, status.HTTP_200_OK)

        self.client.post(reverse('logout-all'), HTTP_AUTHORIZATION=f'Bearer {refreshed["access"]}')

        self.assertEqual(self.get_profile(refreshed['access']).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.refresh(refreshed['refresh']).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_set_elsewhere_also_ends_sessions(self):
        # e.g. an admin resetting the password, or manage.py changepassword.
        access = self.login().data['access']

        self.user.set_password('Admin-set-5512')
        self.user.save()

        self.assertEqual(self.get_profile(access).status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(PASSWORD_HASHERS=[
        'django.contrib.auth.hashers.Argon2PasswordHasher',
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ])
    def test_rehashing_the_password_on_login_keeps_the_session(self):
        from django.contrib.auth.hashers import make_password

        GameUser.objects.filter(pk=self.user.pk).update(password=make_password('Old-pass-4821', hasher='md5'))

        access = self.login().data['access']

        self.assertTrue(GameUser.objects.get(pk=self.user.pk).password.startswith('argon2'))
        self.assertEqual(self.get_profile(access).status_code, status.HTTP_200_OK)

    def test_tokens_issued_before_session_versions_stay_valid(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        legacy = RefreshToken.for_user(self.user)

        self.assertEqual(self.get_profile(str(legacy.access_token)).status_code, status.HTTP_200_OK)
        self.assertEqual(self.refresh(str(legacy)).status_code, status.HTTP_200_OK)


class AccountIdentityTests(APITestCase):
    """Usernames and emails are unique regardless of case; usernames have a fixed format."""

    def setUp(self):
        cache.clear()  # registrations and logins are limited per IP
        GameUser.objects.create_user(username='Hero', email='Hero@Example.com', password='right-pass-123')

    def register(self, username='newbie', email='newbie@example.com'):
        return self.client.post(
            reverse('register'),
            {'username': username, 'email': email, 'password': 'Sturdy-pass-4821'},
            format='json',
        )

    def test_username_taken_in_another_case_is_refused(self):
        response = self.register(username='hERO')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_email_taken_in_another_case_is_refused(self):
        response = self.register(email='hero@example.COM')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_database_rejects_case_variants(self):
        from django.db import IntegrityError, transaction

        for username, email in (('HERO', 'other@example.com'), ('other', 'HERO@example.com')):
            with self.subTest(username=username), self.assertRaises(IntegrityError), transaction.atomic():
                GameUser.objects.create_user(username=username, email=email, password='right-pass-123')

    def test_race_past_validation_still_answers_400(self):
        from .serializers import UserRegistrationSerializer

        # As if another request registered "Hero" between validation and save.
        with mock.patch.object(UserRegistrationSerializer, 'validate_username', lambda self, value: value):
            response = self.register(username='HERO')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertEqual(GameUser.objects.count(), 1)

    def test_username_format(self):
        for username in ('ab', 'a' * 21, 'has space', 'tên', 'semi;colon', 'emoji😀'):
            with self.subTest(username=username):
                response = self.register(username=username)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('username', response.data)
        for username in ('abc', 'a' * 20, 'Player_01', 'dash-name'):
            with self.subTest(username=username):
                cache.clear()
                response = self.register(username=username, email=f'{username}@example.com')
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_login_ignores_username_case(self):
        response = self.client.post(
            reverse('token_obtain_pair'), {'username': 'hero', 'password': 'right-pass-123'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RegistrationPasswordTests(APITestCase):
    def setUp(self):
        cache.clear()  # registrations are throttled per IP

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
