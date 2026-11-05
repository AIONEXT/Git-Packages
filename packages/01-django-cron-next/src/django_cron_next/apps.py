"""
Django app configuration for django-cron-next.
"""

from django.apps import AppConfig


class DjangoCronNextConfig(AppConfig):
    """Configuration for the django-cron-next app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_cron_next"
    verbose_name = "Django Cron Next"

    def ready(self) -> None:
        """Initialize the app when Django starts."""
        # Import signals if any
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass