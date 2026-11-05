"""
Backend implementations for django-cron-next.
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from .models import CronJobModel, CronJobRun
from .jobs import BaseCronJob, JobContext

logger = logging.getLogger(__name__)


@dataclass
class BackendConfig:
    """Configuration for a backend."""

    name: str
    options: Dict[str, Any] = None

    def __post_init__(self):
        if self.options is None:
            self.options = {}


class BaseBackend(ABC):
    """Abstract base class for cron job backends."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Start the backend worker."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the backend worker."""

    @abstractmethod
    async def enqueue_job(self, job: BaseCronJob, scheduled_time: datetime) -> str:
        """Enqueue a job for execution. Returns run ID."""

    @abstractmethod
    async def get_due_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs that are due for execution."""

    @abstractmethod
    async def mark_job_started(self, run_id: str, worker_id: str) -> None:
        """Mark a job as started."""

    @abstractmethod
    async def mark_job_completed(
        self,
        run_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None,
    ) -> None:
        """Mark a job as completed."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Check if backend is running."""


class DatabaseBackend(BaseBackend):
    """Database-backed cron job scheduler using Django ORM."""

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._poll_interval = config.options.get("poll_interval", 30)
        self._batch_size = config.options.get("batch_size", 50)
        self._worker_id = f"db-worker-{uuid.uuid4().hex[:8]}"

    async def start(self) -> None:
        """Start the database polling worker."""
        self._running = True
        logger.info("Database backend started (worker: %s)", self._worker_id)
        asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the database polling worker."""
        self._running = False
        logger.info("Database backend stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop for due jobs."""
        while self._running:
            try:
                due_jobs = await self.get_due_jobs(self._batch_size)
                for job_data in due_jobs:
                    await self._process_job(job_data)
            except Exception as e:
                logger.exception("Error in poll loop: %s", e)

            await asyncio.sleep(self._poll_interval)

    async def _process_job(self, job_data: Dict[str, Any]) -> None:
        """Process a single job."""
        run_id = job_data["run_id"]
        await self.mark_job_started(run_id, self._worker_id)

        try:
            # Load job from database
            job_model = await CronJobModel.objects.aget(id=job_data["job_id"])
            context = JobContext(
                job_name=job_model.name,
                run_id=run_id,
                started_at=time.time(),
                kwargs=job_data.get("kwargs", {}),
                retry_count=job_data.get("retry_count", 0),
                max_retries=job_model.max_retries,
                timeout=job_model.timeout,
            )

            # Execute based on job type
            if job_model.job_type == "async_function":
                from .jobs import AsyncCronJob

                job = AsyncCronJob(
                    name=job_model.name,
                    schedule=job_model.schedule,
                    target=job_model.target,
                    timezone=job_model.timezone,
                    kwargs=job_model.kwargs,
                )
                result = await job.execute_async(context)
            elif job_model.job_type == "management_command":
                from .jobs import ManagementCommandJob

                job = ManagementCommandJob(
                    name=job_model.name,
                    schedule=job_model.schedule,
                    target=job_model.target,
                    timezone=job_model.timezone,
                    kwargs=job_model.kwargs,
                )
                result = await job.execute_async(context)
            else:
                from .jobs import CronJob

                job = CronJob(
                    name=job_model.name,
                    schedule=job_model.schedule,
                    target=job_model.target,
                    timezone=job_model.timezone,
                    kwargs=job_model.kwargs,
                )
                result = job.execute(context)

            await self.mark_job_completed(run_id, "success", result=result)

        except Exception as e:
            logger.exception("Job %s failed: %s", run_id, e)
            await self.mark_job_completed(
                run_id, "failed", error=str(e), traceback=str(e.__traceback__)
            )

    async def enqueue_job(
        self, job: BaseCronJob, scheduled_time: datetime
    ) -> str:
        """Create a CronJobRun record for execution."""
        # Get or create the CronJobModel
        job_model, _ = await CronJobModel.objects.aget_or_create(
            name=job.name,
            defaults={
                "schedule": job.schedule,
                "timezone": job.timezone,
                "job_type": job.__class__.__name__.replace("CronJob", "").lower()
                or "function",
                "target": job.target,
                "kwargs": job.kwargs,
                "enabled": job.enabled,
                "run_on_startup": job.run_on_startup,
                "max_retries": job.max_retries,
                "retry_delay": job.retry_delay,
                "timeout": job.timeout,
            },
        )

        run = await CronJobRun.objects.acreate(
            job=job_model,
            status="pending",
            started_at=scheduled_time,
        )

        # Update next_run on job model
        job_model.last_run = scheduled_time
        job_model.run_count += 1
        await job_model.asave(update_fields=["last_run", "run_count"])

        return str(run.id)

    async def get_due_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs due for execution."""
        now = django_timezone.now()
        due_runs = (
            CronJobRun.objects.select_related("job")
            .filter(status="pending", started_at__lte=now)
            .order_by("started_at")[:limit]
        )

        return [
            {
                "run_id": str(run.id),
                "job_id": str(run.job_id),
                "kwargs": run.job.kwargs,
                "retry_count": run.retry_count,
            }
            async for run in due_runs
        ]

    async def mark_job_started(self, run_id: str, worker_id: str) -> None:
        """Mark job as running."""
        await CronJobRun.objects.filter(id=run_id).aupdate(
            status="running", worker_id=worker_id
        )

    async def mark_job_completed(
        self,
        run_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None,
    ) -> None:
        """Mark job as completed."""
        now = django_timezone.now()
        updates = {
            "status": status,
            "completed_at": now,
        }
        if result is not None:
            updates["result"] = result
        if error is not None:
            updates["error"] = error
        if traceback is not None:
            updates["traceback"] = traceback

        await CronJobRun.objects.filter(id=run_id).aupdate(**updates)

        # Update job model stats
        run = await CronJobRun.objects.select_related("job").aget(id=run_id)
        if status == "success":
            await CronJobModel.objects.filter(id=run.job_id).aupdate(
                failure_count=models.F("failure_count")
            )
        else:
            await CronJobModel.objects.filter(id=run.job_id).aupdate(
                failure_count=models.F("failure_count") + 1,
                last_error=error or "",
            )

    @property
    def is_running(self) -> bool:
        return self._running


class RedisBackend(BaseBackend):
    """Redis-backed cron job scheduler with distributed locking."""

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._redis_url = config.options.get("url", "redis://localhost:6379/0")
        self._key_prefix = config.options.get("key_prefix", "django_cron_next:")
        self._poll_interval = config.options.get("poll_interval", 10)
        self._lock_ttl = config.options.get("lock_ttl", 300)
        self._worker_id = f"redis-worker-{uuid.uuid4().hex[:8]}"
        self._client: Optional[redis.Redis] = None
        self._pubsub = None

    async def start(self) -> None:
        """Start the Redis worker."""
        self._client = redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._running = True
        logger.info("Redis backend started (worker: %s)", self._worker_id)
        asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the Redis worker."""
        self._running = False
        if self._client:
            await self._client.close()
        logger.info("Redis backend stopped")

    async def _acquire_lock(self, lock_key: str) -> bool:
        """Acquire distributed lock for job execution."""
        return await self._client.set(
            f"{self._key_prefix}lock:{lock_key}",
            self._worker_id,
            nx=True,
            ex=self._lock_ttl,
        )

    async def _release_lock(self, lock_key: str) -> None:
        """Release distributed lock."""
        await self._client.delete(f"{self._key_prefix}lock:{lock_key}")

    async def _poll_loop(self) -> None:
        """Main polling loop using Redis sorted sets."""
        while self._running:
            try:
                now = time.time()
                due_jobs = await self._client.zrangebyscore(
                    f"{self._key_prefix}scheduled",
                    "-inf",
                    now,
                    start=0,
                    num=100,
                )

                for job_json in due_jobs:
                    job_data = json.loads(job_json)
                    lock_key = job_data["run_id"]

                    if await self._acquire_lock(lock_key):
                        try:
                            await self._process_redis_job(job_data)
                        finally:
                            await self._release_lock(lock_key)
                    else:
                        # Re-schedule for next poll
                        await self._client.zadd(
                            f"{self._key_prefix}scheduled",
                            {job_json: now + self._poll_interval},
                        )

            except Exception as e:
                logger.exception("Error in Redis poll loop: %s", e)

            await asyncio.sleep(self._poll_interval)

    async def _process_redis_job(self, job_data: Dict[str, Any]) -> None:
        """Process a job from Redis."""
        run_id = job_data["run_id"]
        await self.mark_job_started(run_id, self._worker_id)

        try:
            # Import and execute job
            module_path, func_name = job_data["target"].rsplit(".", 1)
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)

            context = JobContext(
                job_name=job_data["name"],
                run_id=run_id,
                started_at=time.time(),
                kwargs=job_data.get("kwargs", {}),
                retry_count=job_data.get("retry_count", 0),
                max_retries=job_data.get("max_retries", 3),
                timeout=job_data.get("timeout", 300),
            )

            import inspect
            if inspect.iscoroutinefunction(func):
                result = await func(**context.kwargs)
            else:
                result = func(**context.kwargs)

            await self.mark_job_completed(run_id, "success", result=result)

        except Exception as e:
            logger.exception("Redis job %s failed: %s", run_id, e)
            await self.mark_job_completed(
                run_id, "failed", error=str(e)
            )

    async def enqueue_job(
        self, job: BaseCronJob, scheduled_time: datetime
    ) -> str:
        """Enqueue job in Redis sorted set."""
        run_id = str(uuid.uuid4())
        job_data = {
            "run_id": run_id,
            "name": job.name,
            "target": job.target,
            "kwargs": job.kwargs,
            "max_retries": job.max_retries,
            "timeout": job.timeout,
            "retry_count": 0,
        }

        score = scheduled_time.timestamp()
        await self._client.zadd(
            f"{self._key_prefix}scheduled",
            {json.dumps(job_data): score},
        )

        return run_id

    async def get_due_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get due jobs from Redis."""
        now = time.time()
        due_jobs = await self._client.zrangebyscore(
            f"{self._key_prefix}scheduled",
            "-inf",
            now,
            start=0,
            num=limit,
        )
        return [json.loads(j) for j in due_jobs]

    async def mark_job_started(self, run_id: str, worker_id: str) -> None:
        """Mark job as running in Redis."""
        # Remove from scheduled, add to running
        pass  # Implementation depends on job data structure

    async def mark_job_completed(
        self,
        run_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None,
    ) -> None:
        """Mark job as completed in Redis."""
        # Store result in Redis for retrieval
        result_data = {
            "run_id": run_id,
            "status": status,
            "completed_at": time.time(),
            "result": result,
            "error": error,
            "traceback": traceback,
        }
        await self._client.set(
            f"{self._key_prefix}result:{run_id}",
            json.dumps(result_data),
            ex=86400,  # 24 hours
        )

    @property
    def is_running(self) -> bool:
        return self._running


def get_backend(backend_name: str, options: Optional[Dict[str, Any]] = None) -> BaseBackend:
    """Factory function to get a backend instance."""
    config = BackendConfig(name=backend_name, options=options or {})

    if backend_name == "database":
        return DatabaseBackend(config)
    elif backend_name == "redis":
        return RedisBackend(config)
    else:
        raise ValueError(f"Unknown backend: {backend_name}")