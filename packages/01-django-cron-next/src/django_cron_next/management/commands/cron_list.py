"""
Django management command to list cron jobs.
"""

import asyncio
from django.core.management.base import BaseCommand
from ...scheduler import get_scheduler
from ...models import CronJobModel


class Command(BaseCommand):
    """List all cron jobs."""

    help = "List all registered cron jobs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--backend",
            default="database",
            choices=["database", "redis"],
            help="Backend to use",
        )
        parser.add_argument(
            "--format",
            choices=["table", "json", "simple"],
            default="table",
            help="Output format",
        )
        parser.add_argument(
            "--enabled-only",
            action="store_true",
            help="Show only enabled jobs",
        )
        parser.add_argument(
            "--from-db",
            action="store_true",
            help="List jobs from database instead of scheduler",
        )

    def handle(self, *args, **options):
        if options["from_db"]:
            self._list_from_db(options)
        else:
            asyncio.run(self._list_from_scheduler(options))

    def _list_from_db(self, options):
        """List jobs from database."""
        queryset = CronJobModel.objects.all()
        if options["enabled_only"]:
            queryset = queryset.filter(enabled=True)

        jobs = list(queryset.order_by("name"))

        if options["format"] == "json":
            import json
            data = [
                {
                    "name": job.name,
                    "schedule": job.schedule,
                    "timezone": job.timezone,
                    "job_type": job.job_type,
                    "target": job.target,
                    "enabled": job.enabled,
                    "run_on_startup": job.run_on_startup,
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "next_run": job.next_run.isoformat() if job.next_run else None,
                    "run_count": job.run_count,
                    "failure_count": job.failure_count,
                }
                for job in jobs
            ]
            self.stdout.write(json.dumps(data, indent=2))
        elif options["format"] == "simple":
            for job in jobs:
                status = "ENABLED" if job.enabled else "DISABLED"
                self.stdout.write(f"{job.name} [{status}] - {job.schedule}")
        else:
            from django.utils.html import format_html
            self.stdout.write(f"{'NAME':<40} {'SCHEDULE':<20} {'TYPE':<20} {'STATUS':<10} {'NEXT RUN'}")
            self.stdout.write("-" * 110)
            for job in jobs:
                status = "ENABLED" if job.enabled else "DISABLED"
                next_run = job.next_run.strftime("%Y-%m-%d %H:%M") if job.next_run else "Never"
                self.stdout.write(
                    f"{job.name:<40} {job.schedule:<20} {job.job_type:<20} {status:<10} {next_run}"
                )

    async def _list_from_scheduler(self, options):
        """List jobs from scheduler."""
        scheduler = get_scheduler(backend=options["backend"])
        jobs = scheduler.list_jobs()

        if options["enabled_only"]:
            jobs = [j for j in jobs if j.enabled]

        if options["format"] == "json":
            import json
            data = [
                {
                    "name": job.name,
                    "schedule": job.schedule,
                    "timezone": job.timezone,
                    "target": job.target,
                    "enabled": job.enabled,
                    "run_on_startup": job.run_on_startup,
                    "max_retries": job.max_retries,
                    "timeout": job.timeout,
                }
                for job in jobs
            ]
            self.stdout.write(json.dumps(data, indent=2))
        elif options["format"] == "simple":
            for job in jobs:
                status = "ENABLED" if job.enabled else "DISABLED"
                self.stdout.write(f"{job.name} [{status}] - {job.schedule}")
        else:
            self.stdout.write(f"{'NAME':<40} {'SCHEDULE':<20} {'TARGET':<30} {'STATUS'}")
            self.stdout.write("-" * 100)
            for job in jobs:
                status = "ENABLED" if job.enabled else "DISABLED"
                target = job.target[:28] + ".." if len(job.target) > 30 else job.target
                self.stdout.write(f"{job.name:<40} {job.schedule:<20} {target:<30} {status}")