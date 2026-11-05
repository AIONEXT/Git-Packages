"""
Django management command to stop the cron scheduler.
"""

import asyncio

from django.core.management.base import BaseCommand

from ...scheduler import stop_scheduler


class Command(BaseCommand):
    """Stop the cron scheduler."""

    help = "Stop the django-cron-next scheduler"

    def handle(self, *args, **options):
        self.stdout.write("Stopping cron scheduler...")

        async def run_stop():
            await stop_scheduler()

        try:
            asyncio.run(run_stop())
            self.stdout.write(self.style.SUCCESS("Scheduler stopped"))
        except Exception as e:
            self.stderr.write(f"Error: {e}")