"""
Main scheduler for django-cron-next.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from croniter import croniter
from django.utils import timezone as django_timezone

from .backends import BaseBackend, DatabaseBackend, RedisBackend, get_backend
from .jobs import BaseCronJob, CronJob, AsyncCronJob, ManagementCommandJob
from .models import CronJobModel

logger = logging.getLogger(__name__)


class CronScheduler:
    """Main cron scheduler coordinating jobs and backends."""

    def __init__(
        self,
        backend: str = "database",
        backend_options: Optional[Dict[str, Any]] = None,
    ):
        self.backend: BaseBackend = get_backend(backend, backend_options)
        self._jobs: Dict[str, BaseCronJob] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    def add_job(
        self,
        name: str,
        schedule: str,
        target: str,
        job_type: str = "function",
        timezone: str = "UTC",
        kwargs: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        run_on_startup: bool = False,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300,
    ) -> BaseCronJob:
        """Add a new cron job to the scheduler."""
        if job_type == "async_function":
            job = AsyncCronJob(
                name=name,
                schedule=schedule,
                target=target,
                timezone=timezone,
                kwargs=kwargs,
                enabled=enabled,
                run_on_startup=run_on_startup,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
            )
        elif job_type == "management_command":
            job = ManagementCommandJob(
                name=name,
                schedule=schedule,
                target=target,
                timezone=timezone,
                kwargs=kwargs,
                enabled=enabled,
                run_on_startup=run_on_startup,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
            )
        else:
            job = CronJob(
                name=name,
                schedule=schedule,
                target=target,
                timezone=timezone,
                kwargs=kwargs,
                enabled=enabled,
                run_on_startup=run_on_startup,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
            )

        self._jobs[name] = job
        logger.info("Added job: %s (%s)", name, schedule)
        return job

    def remove_job(self, name: str) -> bool:
        """Remove a job from the scheduler."""
        if name in self._jobs:
            del self._jobs[name]
            logger.info("Removed job: %s", name)
            return True
        return False

    def get_job(self, name: str) -> Optional[BaseCronJob]:
        """Get a job by name."""
        return self._jobs.get(name)

    def list_jobs(self) -> List[BaseCronJob]:
        """List all registered jobs."""
        return list(self._jobs.values())

    def _get_next_run(self, schedule: str, timezone_str: str = "UTC") -> datetime:
        """Calculate next run time for a cron schedule."""
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone_str)
        except Exception:
            tz = timezone.utc

        now = datetime.now(tz)
        cron = croniter(schedule, now)
        next_run = cron.get_next(datetime)
        return next_run

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        await self.backend.start()

        # Schedule all enabled jobs
        for job in self._jobs.values():
            if job.enabled:
                await self._schedule_job(job)

        # Start the main scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started with %d jobs", len(self._jobs))

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        await self.backend.stop()
        logger.info("Scheduler stopped")

    async def _schedule_job(self, job: BaseCronJob) -> None:
        """Schedule a single job for its next run."""
        next_run = self._get_next_run(job.schedule, job.timezone)
        run_id = await self.backend.enqueue_job(job, next_run)
        logger.debug("Scheduled job %s for %s (run_id: %s)", job.name, next_run, run_id)

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - check for jobs to reschedule."""
        while self._running:
            try:
                # Check for completed jobs and reschedule
                # This is handled by the backend polling loop
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in scheduler loop: %s", e)
                await asyncio.sleep(10)

    async def run_job_now(self, name: str) -> str:
        """Run a job immediately (outside of schedule)."""
        job = self._jobs.get(name)
        if not job:
            raise ValueError(f"Job not found: {name}")

        now = django_timezone.now()
        run_id = await self.backend.enqueue_job(job, now)
        logger.info("Triggered immediate run of job %s (run_id: %s)", name, run_id)
        return run_id

    async def sync_from_database(self) -> int:
        """Sync jobs from database models."""
        count = 0
        async for job_model in CronJobModel.objects.filter(enabled=True):
            job_type_map = {
                "function": "function",
                "async_function": "async_function",
                "management_command": "management_command",
            }
            job_type = job_type_map.get(job_model.job_type, "function")

            self.add_job(
                name=job_model.name,
                schedule=job_model.schedule,
                target=job_model.target,
                job_type=job_type,
                timezone=job_model.timezone,
                kwargs=job_model.kwargs,
                enabled=job_model.enabled,
                run_on_startup=job_model.run_on_startup,
                max_retries=job_model.max_retries,
                retry_delay=job_model.retry_delay,
                timeout=job_model.timeout,
            )
            count += 1

        logger.info("Synced %d jobs from database", count)
        return count


# Global scheduler instance
_scheduler: Optional[CronScheduler] = None


def get_scheduler(
    backend: str = "database",
    backend_options: Optional[Dict[str, Any]] = None,
) -> CronScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CronScheduler(backend=backend, backend_options=backend_options)
    return _scheduler


async def start_scheduler(
    backend: str = "database",
    backend_options: Optional[Dict[str, Any]] = None,
) -> CronScheduler:
    """Start the global scheduler."""
    scheduler = get_scheduler(backend, backend_options)
    await scheduler.start()
    return scheduler


async def stop_scheduler() -> None:
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None