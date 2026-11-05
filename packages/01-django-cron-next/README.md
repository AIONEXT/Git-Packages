# django-cron-next

Modern async cron scheduler for Django 4.2+/5.x — a complete rewrite of the abandoned `django-crontab` (212k downloads/month, last release 2016).

## Features

- **Full async/await support** — Native async job execution with `AsyncCronJob`
- **Multiple backends** — Database (Django ORM) and Redis (distributed)
- **Timezone-aware scheduling** — IANA timezone support via `zoneinfo`
- **Job types** — Sync functions, async functions, Django management commands
- **Django admin integration** — Manage jobs through Django admin
- **Management commands** — `cron_start`, `cron_stop`, `cron_list`, `cron_run`
- **Retry logic** — Configurable retries with exponential backoff
- **Monitoring** — Job run history, success/failure tracking

## Installation

```bash
pip install django-cron-next
```

## Quick Start

### 1. Add to `INSTALLED_APPS`

```python
# settings.py
INSTALLED_APPS = [
    ...
    "django_cron_next",
]
```

### 2. Run migrations

```bash
python manage.py migrate
```

### 3. Define cron jobs

```python
# cron_jobs.py
from django_cron_next import CronJob, AsyncCronJob, ManagementCommandJob

# Synchronous function job
CronJob(
    name="daily_cleanup",
    schedule="0 2 * * *",  # Daily at 2 AM UTC
    target="myapp.tasks.cleanup_old_records",
    kwargs={"days": 30},
)

# Asynchronous function job
AsyncCronJob(
    name="fetch_external_data",
    schedule="*/15 * * * *",  # Every 15 minutes
    target="myapp.tasks.fetch_data_async",
    timezone="America/New_York",
)

# Django management command
ManagementCommandJob(
    name="database_backup",
    schedule="0 3 * * 0",  # Weekly on Sunday at 3 AM
    target="dbbackup",
    kwargs={"clean": True},
)
```

### 4. Register jobs in `apps.py`

```python
# myapp/apps.py
from django.apps import AppConfig
from django_cron_next import get_scheduler

class MyAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "myapp"

    def ready(self):
        from . import cron_jobs  # noqa: F401
        # Jobs auto-register on import
```

### 5. Start the scheduler

```bash
# Development
python manage.py cron_start --daemon

# Production (with Redis)
python manage.py cron_start --backend redis --redis-url redis://localhost:6379/0 --daemon
```

## Configuration

### Settings

```python
# settings.py
DJANGO_CRON_NEXT = {
    "BACKEND": "database",  # or "redis"
    "BACKEND_OPTIONS": {
        "poll_interval": 30,  # seconds (database backend)
        # Redis options:
        # "url": "redis://localhost:6379/0",
        # "key_prefix": "myapp:cron:",
        # "lock_ttl": 300,
    },
    "DEFAULT_TIMEZONE": "UTC",
}
```

### Redis Backend

```python
# For distributed deployments
DJANGO_CRON_NEXT = {
    "BACKEND": "redis",
    "BACKEND_OPTIONS": {
        "url": "redis://user:pass@redis-host:6379/0",
        "key_prefix": "myapp:cron:",
        "poll_interval": 10,
        "lock_ttl": 300,
    },
}
```

## Management Commands

```bash
# Start scheduler (blocking)
python manage.py cron_start --daemon

# Stop scheduler
python manage.py cron_stop

# List jobs
python manage.py cron_list --format table
python manage.py cron_list --format json
python manage.py cron_list --from-db

# Run job immediately
python manage.py cron_run my_job_name
python manage.py cron_run my_job_name --async
python manage.py cron_run my_job_name --kwargs '{"key": "value"}'
```

## Job Types

### CronJob (Synchronous)

```python
CronJob(
    name="sync_job",
    schedule="0 * * * *",
    target="myapp.tasks.process_data",
    kwargs={"batch_size": 100},
    timezone="UTC",
    enabled=True,
    max_retries=3,
    retry_delay=60,
    timeout=300,
)
```

### AsyncCronJob (Asynchronous)

```python
AsyncCronJob(
    name="async_job",
    schedule="*/5 * * * *",
    target="myapp.tasks.async_fetch",
    timezone="Europe/London",
    # Native async execution, no thread pool overhead
)
```

### ManagementCommandJob

```python
ManagementCommandJob(
    name="backup_job",
    schedule="0 1 * * *",
    target="dbbackup",
    kwargs={"clean": True, "compress": True},
)
```

## Admin Interface

```python
# admin.py
from django.contrib import admin
from django_cron_next.models import CronJobModel, CronJobRun

@admin.register(CronJobModel)
class CronJobModelAdmin(admin.ModelAdmin):
    list_display = ["name", "schedule", "enabled", "last_run", "next_run", "run_count"]
    list_filter = ["enabled", "job_type"]
    search_fields = ["name", "target"]
    readonly_fields = ["last_run", "next_run", "run_count", "failure_count"]

@admin.register(CronJobRun)
class CronJobRunAdmin(admin.ModelAdmin):
    list_display = ["job", "status", "started_at", "completed_at", "duration_ms"]
    list_filter = ["status", "job"]
    readonly_fields = ["started_at", "completed_at", "duration_ms", "result", "error"]
```

## Monitoring

### Job Run History

```python
from django_cron_next.models import CronJobRun

# Get recent runs
recent_runs = CronJobRun.objects.filter(job__name="daily_cleanup").order_by("-started_at")[:10]

# Failed jobs
failed_runs = CronJobRun.objects.filter(status="failed").select_related("job")
```

### Prometheus Metrics (Optional)

```python
# Add to your metrics endpoint
from django_cron_next.models import CronJobModel, CronJobRun

def cron_metrics():
    return {
        "total_jobs": CronJobModel.objects.count(),
        "enabled_jobs": CronJobModel.objects.filter(enabled=True).count(),
        "failed_runs_24h": CronJobRun.objects.filter(
            status="failed",
            started_at__gte=timezone.now() - timedelta(hours=24)
        ).count(),
    }
```

## Migration from django-crontab

```python
# Old django-crontab style
CRONJOBS = [
    ("0 2 * * *", "myapp.tasks.cleanup"),
]

# New django-cron-next style
from django_cron_next import CronJob
CronJob(
    name="cleanup",
    schedule="0 2 * * *",
    target="myapp.tasks.cleanup",
)
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
ruff format .

# Type check
mypy .

# Security
bandit -r .
```

## License

MIT License — see LICENSE file for details.

## Changelog

### 0.1.0 (2026-11-04)
- Initial release
- Async/await support
- Database and Redis backends
- Management commands
- Django admin integration