from django.apps import AppConfig


class StudioConfig(AppConfig):
    """Game data editor for staff at /studio/, friendlier than the Django admin."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.studio'
    verbose_name = 'Studio'
