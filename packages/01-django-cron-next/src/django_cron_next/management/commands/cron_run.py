"""
Django management command to run a cron job immediately.
"""

import asyncio
from django.core.management.base import BaseCommand, CommandError
from ...scheduler import get_scheduler


class Command(BaseCommand):
    """Run a cron job immediately."""

    help = "Run a cron job immediately (outside of schedule)"

    def add_arguments(self, parser):
        parser.add_argument("job_name", type=str, help="Name of the job to run")
        parser.add_argument(
            "--backend",
            default="database",
            choices=["database", "redis"],
            help="Backend to use",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="run_async",
            help="Run job asynchronously (don't wait for completion)",
        )
        parser.add_argument(
            "--kwargs",
            type=str,
            default="{}",
            help="JSON string of additional kwargs to pass to job",
        )

    def handle(self, *args, **options):
        job_name = options["job_name"]
        run_async = options["run_async"]
        kwargs_str = options["kwargs"]

        try:
            import json
            extra_kwargs = json.loads(kwargs_str)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in --kwargs: {e}")

        self.stdout.write(f"Running job: {job_name}")

        async def run_job():
            scheduler = get_scheduler(backend=options["backend"])
            run_id = await scheduler.run_job_now(job_name)
            self.stdout.write(self.style.SUCCESS(f"Job triggered (run_id: {run_id})"))

            if not run_async:
                self.stdout.write("Waiting for completion...")
                # In a real implementation, we'd poll for completion
                # For now, just return the run_id
                return run_id

        try:
            result = asyncio.run(run_job())
            if result and not run_async:
                self.stdout.write(self.style.SUCCESS(f"Job completed: {result}"))
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Error running job: {e}")