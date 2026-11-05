"""
Database models for django-cron-next.
"""

import uuid
from datetime import timezone
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone as django_timezone


class CronJobModel(models.Model):
    """Model representing a scheduled cron job."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    schedule = models.CharField(
        max_length=100,
        help_text="Cron expression (e.g., '0 2 * * *' for daily at 2 AM)",
    )
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="IANA timezone name (e.g., 'America/New_York', 'Europe/London')",
    )
    job_type = models.CharField(
        max_length=50,
        choices=[
            ("function", "Python Function"),
            ("async_function", "Async Python Function"),
            ("management_command", "Django Management Command"),
        ],
        default="function",
    )
    target = models.CharField(
        max_length=500,
        help_text="Import path to function or management command name",
    )
    kwargs = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    run_on_startup = models.BooleanField(default=False)
    max_retries = models.PositiveIntegerField(default=3)
    retry_delay = models.PositiveIntegerField(
        default=60, help_text="Delay between retries in seconds"
    )
    timeout = models.PositiveIntegerField(
        default=300, help_text="Job timeout in seconds"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True, db_index=True)
    run_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "django_cron_next_job"
        verbose_name = "Cron Job"
        verbose_name_plural = "Cron Jobs"
        ordering = ["next_run", "name"]
        indexes = [
            models.Index(fields=["enabled", "next_run"]),
            models.Index(fields=["job_type", "enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.schedule})"


class CronJobRun(models.Model):
    """Model representing a single execution of a cron job."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        CronJobModel,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("running", "Running"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("timeout", "Timeout"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        db_index=True,
    )
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    traceback = models.TextField(blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    worker_id = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "django_cron_next_job_run"
        verbose_name = "Cron Job Run"
        verbose_name_plural = "Cron Job Runs"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["status", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.job.name} - {self.status} at {self.started_at}"