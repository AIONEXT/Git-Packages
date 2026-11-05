"""
django-cron-next: Modern async cron scheduler for Django 4.2+/5.x

A rewrite of the abandoned django-crontab with:
- Full async/await support
- Redis and PostgreSQL backends
- Timezone-aware scheduling (ZoneInfo)
- Django admin integration
- Management commands for cron control
"""

__version__ = "0.1.0"
__author__ = "AIONEXT"
__email__ = "aionext@outlook.com"
__license__ = "MIT"

from .scheduler import CronScheduler
from .jobs import CronJob, AsyncCronJob, ManagementCommandJob
from .backends import RedisBackend, DatabaseBackend
from .management.commands import cron_start, cron_stop, cron_list, cron_run

__all__ = [
    "CronScheduler",
    "CronJob",
    "AsyncCronJob",
    "ManagementCommandJob",
    "RedisBackend",
    "DatabaseBackend",
    "cron_start",
    "cron_stop",
    "cron_list",
    "cron_run",
]

default_app_config = "django_cron_next.apps.DjangoCronNextConfig"