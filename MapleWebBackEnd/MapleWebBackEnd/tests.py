import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.users.models import GameUser

PROJECT_DIR = Path(__file__).resolve().parent.parent


def settings_under(env):
    """Security settings as a fresh process sees them with this environment."""
    script = (
        'import json, django; django.setup(); from django.conf import settings as s; '
        'print(json.dumps({k: getattr(s, k) for k in ('
        '"SECURE_PROXY_SSL_HEADER", "CSRF_TRUSTED_ORIGINS", "SESSION_COOKIE_SECURE", '
        '"CSRF_COOKIE_SECURE", "SECURE_HSTS_SECONDS", "SECURE_SSL_REDIRECT")}))'
    )
    base = {key: value for key, value in os.environ.items() if not key.startswith(('NUM_PROXIES', 'DEBUG', 'CSRF_', 'SECURE_'))}
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=PROJECT_DIR, capture_output=True, text=True, check=True,
        env={**base, 'DJANGO_SETTINGS_MODULE': 'MapleWebBackEnd.settings', 'SECRET_KEY': 'test-key', **env},
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


class ProductionSettingsTests(SimpleTestCase):
    def test_behind_a_proxy_https_comes_from_the_proxy_header(self):
        values = settings_under({'NUM_PROXIES': '1', 'DEBUG': 'False'})

        self.assertEqual(values['SECURE_PROXY_SSL_HEADER'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertTrue(values['SESSION_COOKIE_SECURE'])
        self.assertTrue(values['CSRF_COOKIE_SECURE'])

    def test_local_development_keeps_plain_http(self):
        values = settings_under({'NUM_PROXIES': '0', 'DEBUG': 'True'})

        self.assertIsNone(values['SECURE_PROXY_SSL_HEADER'])
        self.assertFalse(values['SESSION_COOKIE_SECURE'])
        self.assertEqual((values['SECURE_HSTS_SECONDS'], values['SECURE_SSL_REDIRECT']), (0, False))

    def test_trusted_origins_and_hsts_come_from_the_environment(self):
        values = settings_under({
            'DEBUG': 'False', 'CSRF_TRUSTED_ORIGINS': 'https://maple.onrender.com,https://admin.example.com',
            'SECURE_HSTS_SECONDS': '3600',
        })

        self.assertEqual(values['CSRF_TRUSTED_ORIGINS'], ['https://maple.onrender.com', 'https://admin.example.com'])
        self.assertEqual(values['SECURE_HSTS_SECONDS'], 3600)


@override_settings(ALLOWED_HOSTS=['maple.onrender.com'])
class ProxiedAdminLoginTests(TestCase):
    """On a host that ends HTTPS at its proxy, admin/Studio forms must pass the CSRF origin check."""

    def setUp(self):
        GameUser.objects.create_superuser(username='boss', email='boss@example.com', password='Pass-12345')
        self.client = Client(enforce_csrf_checks=True)

    def login(self):
        page = self.client.get(reverse('admin:login'), HTTP_HOST='maple.onrender.com', HTTP_X_FORWARDED_PROTO='https')
        token = page.cookies['csrftoken'].value
        return self.client.post(
            reverse('admin:login'), {'username': 'boss', 'password': 'Pass-12345', 'csrfmiddlewaretoken': token},
            HTTP_HOST='maple.onrender.com', HTTP_X_FORWARDED_PROTO='https', HTTP_ORIGIN='https://maple.onrender.com',
            HTTP_REFERER='https://maple.onrender.com/admin/login/',
        )

    def test_without_trusting_the_proxy_the_login_is_refused(self):
        with override_settings(SECURE_PROXY_SSL_HEADER=None):
            self.assertEqual(self.login().status_code, 403)

    def test_trusting_the_proxy_header_lets_the_login_through(self):
        with override_settings(SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')):
            self.assertEqual(self.login().status_code, 302)
