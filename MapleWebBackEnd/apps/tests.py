import importlib
import inspect

from django.apps import apps as django_apps
from django.test import SimpleTestCase
from rest_framework import serializers


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
