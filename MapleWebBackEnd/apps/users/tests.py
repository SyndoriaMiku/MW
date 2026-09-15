from django.test import SimpleTestCase
from django.urls import reverse


class SessionRoutingTests(SimpleTestCase):
    def test_bootstrap_endpoint_is_routed(self):
        self.assertEqual(reverse('session-bootstrap'), '/api/session/bootstrap/')
