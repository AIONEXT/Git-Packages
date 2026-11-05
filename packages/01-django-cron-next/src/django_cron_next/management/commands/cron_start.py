"""
Django management command to start the cron scheduler.
"""

import asyncio
import logging
import signal
import sys

from django.core.management.base import BaseCommand

from ...scheduler import get_scheduler, start_scheduler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Start the cron scheduler."""

    help = "Start the django-cron-next scheduler"

    def add_arguments(self, parser):
        parser.add_argument(
            "--backend",
            default="database",
            choices=["database", "redis"],
            help="Backend to use for job scheduling",
        )
        parser.add_argument(
            "--redis-url",
            default=None,
            help="Redis URL (for redis backend)",
        )
        parser.add_argument(
            "--poll-interval",
            type=int,
            default=30,
            help="Poll interval in seconds (database backend)",
        )
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run as daemon (blocking)",
        )
        parser.add_argument(
            "--sync-db",
            action="store_true",
            help="Sync jobs from database before starting",
        )

    def handle(self, *args, **options):
        backend = options["backend"]
        backend_options = {}

        if backend == "redis":
            redis_url = options["redis_url"]
            if redis_url:
                backend_options["url"] = redis_url
        else:
            backend_options["poll_interval"] = options["poll_interval"]

        self.stdout.write(
            self.style.SUCCESS(f"Starting cron scheduler with {backend} backend...")
        )

        async def run_scheduler():
            scheduler = await start_scheduler(backend=backend, backend_options=backend_options)

            if options["sync_db"]:
                count = await scheduler.sync_from_database()
                self.stdout.write(f"Synced {count} jobs from database")

            if options["daemon"]:
                # Set up signal handlers
                loop = asyncio.get_running_loop()

                def signal_handler():
                    self.stdout.write(self.style.WARNING("Shutting down..."))
                    asyncio.create_task(scheduler.stop())

                for sig in (signal.SIGTERM, signal.SIGINT):
                    try:
                        loop.add_signal_handler(sig, signal_handler)
                    except NotImplementedError:
                        # Windows doesn't support add_signal_handler
                        pass

                # Keep running
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    pass
            else:
                self.stdout.write(
                    self.style.SUCCESS("Scheduler started in background")
                )

        try:
            asyncio.run(run_scheduler())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Scheduler stopped"))
        except Exception as e:
            self.stderr.write(f"Error: {e}")
            sys.exit(1)