from django.test import SimpleTestCase

from .urls import urlpatterns


class CharacterRoutingTests(SimpleTestCase):
    def test_my_skills_endpoint_is_routed(self):
        route_names = {pattern.name for pattern in urlpatterns}
        self.assertIn('my-character-skills', route_names)
