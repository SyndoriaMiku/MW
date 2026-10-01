import importlib
import inspect
import warnings

from django.apps import apps as django_apps
from django.core.cache import cache
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import serializers
from rest_framework.test import APITestCase

from apps.api_errors import build_error_envelope
from apps.characters.models import Character
from apps.users.models import GameUser


class ExplicitSerializerFieldTests(SimpleTestCase):
    """New model columns must not reach the API unless a serializer lists them."""

    def test_model_serializers_list_their_fields(self):
        offenders = []
        for config in django_apps.get_app_configs():
            if not config.name.startswith('apps.'):
                continue
            try:
                module = importlib.import_module(f'{config.name}.serializers')
            except ModuleNotFoundError:
                continue
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__ or not issubclass(cls, serializers.ModelSerializer):
                    continue
                meta = getattr(cls, 'Meta', None)
                if getattr(meta, 'fields', None) == serializers.ALL_FIELDS or hasattr(meta, 'exclude'):
                    offenders.append(f'{module.__name__}.{name}')

        self.assertEqual(offenders, [])


class ErrorEnvelopeTests(APITestCase):
    """Every 4xx/5xx body carries code/message/fields and keeps its legacy keys."""

    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='envelope', email='envelope@example.com', password='test-pass-123'
        )
        self.user.character = Character.objects.create(name='Envelope')
        self.user.save(update_fields=['character'])

    def test_authentication_error(self):
        body = self.client.get('/api/market/').json()

        self.assertEqual(body['code'], 'not_authenticated')
        self.assertEqual(body['message'], body['detail'])
        self.assertEqual(body['fields'], {})

    def test_manual_detail_response(self):
        self.client.force_authenticate(self.user)

        body = self.client.get('/api/battles/nope1234/').json()

        self.assertEqual(body['code'], 'not_found')
        self.assertEqual(body['message'], 'Battle not found.')
        self.assertEqual(body['detail'], 'Battle not found.')

    def test_field_validation_errors(self):
        cache.clear()  # registrations are throttled per IP
        response = self.client.post(
            reverse('register'),
            {'username': 'envelope2', 'email': 'e2@example.com', 'password': '1'},
            format='json',
        )
        body = response.json()

        self.assertEqual(body['code'], 'validation_error')
        self.assertIn('password', body['fields'])
        self.assertEqual(body['message'], body['fields']['password'][0])
        self.assertEqual(body['password'], body['fields']['password'])

    def test_existing_code_and_message_keys_are_kept(self):
        self.client.force_authenticate(self.user)

        body = self.client.post(
            reverse('lumen-api', args=['ascend']), {'inventory_item_id': 999999}, format='json'
        ).json()

        self.assertEqual(body['code'], 'bad_request')
        self.assertEqual(body['message'], 'Item not found or not owned.')
        self.assertFalse(body['success'])

    def test_list_validation_error_becomes_non_field_errors(self):
        body = build_error_envelope(['This item cannot be traded.'], 400)

        self.assertEqual(body['code'], 'validation_error')
        self.assertEqual(body['message'], 'This item cannot be traded.')
        self.assertEqual(body['non_field_errors'], ['This item cannot be traded.'])

    def test_explicit_code_wins(self):
        body = build_error_envelope({'detail': 'Not enough.', 'code': 'insufficient_materials'}, 400)

        self.assertEqual(body['code'], 'insufficient_materials')

    def test_success_bodies_are_untouched(self):
        self.client.force_authenticate(self.user)

        body = self.client.get(reverse('session-bootstrap')).json()

        self.assertNotIn('code', body)


class ApiDocumentationTests(APITestCase):
    def test_openapi_schema_generates_without_view_errors(self):
        with self.assertNoLogs('drf_yasg', level='WARNING'):
            response = self.client.get('/swagger/?format=openapi')

        self.assertEqual(response.status_code, 200)


class PaginationOrderTests(APITestCase):
    def test_paginated_lists_have_a_stable_order(self):
        user = GameUser.objects.create_user(
            username='pager', email='pager@example.com', password='test-pass-123'
        )
        user.character = Character.objects.create(name='Pager')
        user.save(update_fields=['character'])
        self.client.force_authenticate(user)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            for url in ('/api/classes/', '/api/classes/jobs/', '/api/inventory/'):
                self.assertEqual(self.client.get(url).status_code, 200)

        unordered = [str(w.message) for w in caught if 'UnorderedObjectListWarning' in type(w.message).__name__]
        self.assertEqual(unordered, [])
