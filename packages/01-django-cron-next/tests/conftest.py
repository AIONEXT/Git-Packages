"""
Pytest configuration for django-cron-next tests.
"""

import os
import sys

import django
from django.conf import settings

# Configure Django settings before importing anything else
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="test-secret-key-for-testing-only",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django_cron_next",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        USE_TZ=True,
        TIME_ZONE="UTC",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()

import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup():
    """Create database tables."""
    call_command("migrate", "--run-syncdb", verbosity=0)
    yield
    # Cleanup happens automatically with in-memory SQLite


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()