"""
Job definitions for django-cron-next.
"""

import asyncio
import importlib
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class JobContext:
    """Context passed to job execution."""

    job_name: str
    run_id: str
    started_at: float
    kwargs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300


class BaseCronJob(ABC):
    """Abstract base class for all cron jobs."""

    def __init__(
        self,
        name: str,
        schedule: str,
        timezone: str = "UTC",
        kwargs: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        run_on_startup: bool = False,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300,
    ):
        self.name = name
        self.schedule = schedule
        self.timezone = timezone
        self.kwargs = kwargs or {}
        self.enabled = enabled
        self.run_on_startup = run_on_startup
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    @abstractmethod
    def execute(self, context: JobContext) -> Any:
        """Execute the job synchronously."""
        ...

    async def execute_async(self, context: JobContext) -> Any:
        """Execute the job asynchronously. Override for native async support."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, context)

    def validate(self) -> bool:
        """Validate job configuration."""
        return bool(self.name and self.schedule and self.target)

    @property
    @abstractmethod
    def target(self) -> str:
        """Import path or identifier for the job target."""
        ...


class CronJob(BaseCronJob):
    """Synchronous function-based cron job."""

    def __init__(
        self,
        name: str,
        schedule: str,
        target: str,
        timezone: str = "UTC",
        kwargs: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        run_on_startup: bool = False,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300,
    ):
        super().__init__(
            name=name,
            schedule=schedule,
            timezone=timezone,
            kwargs=kwargs,
            enabled=enabled,
            run_on_startup=run_on_startup,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
        )
        self._target = target
        self._func: Optional[Callable] = None

    @property
    def target(self) -> str:
        return self._target

    def _load_function(self) -> Callable:
        """Load the target function from import path."""
        if self._func is not None:
            return self._func

        try:
            module_path, func_name = self._target.rsplit(".", 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            if not callable(func):
                raise ValueError(f"{self._target} is not callable")
            self._func = func
            return func
        except (ImportError, AttributeError, ValueError) as e:
            logger.error("Failed to load function %s: %s", self._target, e)
            raise

    def execute(self, context: JobContext) -> Any:
        """Execute the synchronous function."""
        func = self._load_function()
        merged_kwargs = {**self.kwargs, **context.kwargs}
        return func(**merged_kwargs)


class AsyncCronJob(BaseCronJob):
    """Asynchronous function-based cron job."""

    def __init__(
        self,
        name: str,
        schedule: str,
        target: str,
        timezone: str = "UTC",
        kwargs: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        run_on_startup: bool = False,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300,
    ):
        super().__init__(
            name=name,
            schedule=schedule,
            timezone=timezone,
            kwargs=kwargs,
            enabled=enabled,
            run_on_startup=run_on_startup,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
        )
        self._target = target
        self._func: Optional[Callable] = None

    @property
    def target(self) -> str:
        return self._target

    def _load_function(self) -> Callable:
        """Load the target async function from import path."""
        if self._func is not None:
            return self._func

        try:
            module_path, func_name = self._target.rsplit(".", 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            if not callable(func):
                raise ValueError(f"{self._target} is not callable")
            if not inspect.iscoroutinefunction(func):
                logger.warning(
                    "Target %s is not an async function; will run in executor",
                    self._target,
                )
            self._func = func
            return func
        except (ImportError, AttributeError, ValueError) as e:
            logger.error("Failed to load async function %s: %s", self._target, e)
            raise

    async def execute_async(self, context: JobContext) -> Any:
        """Execute the async function natively."""
        func = self._load_function()
        merged_kwargs = {**self.kwargs, **context.kwargs}

        if inspect.iscoroutinefunction(func):
            return await func(**merged_kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, **merged_kwargs)

    def execute(self, context: JobContext) -> Any:
        """Execute by running async version in event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.execute_async(context))


class ManagementCommandJob(BaseCronJob):
    """Django management command cron job."""

    def __init__(
        self,
        name: str,
        schedule: str,
        target: str,
        timezone: str = "UTC",
        kwargs: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        run_on_startup: bool = False,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300,
    ):
        super().__init__(
            name=name,
            schedule=schedule,
            timezone=timezone,
            kwargs=kwargs,
            enabled=enabled,
            run_on_startup=run_on_startup,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
        )
        self._target = target

    @property
    def target(self) -> str:
        return self._target

    def execute(self, context: JobContext) -> Any:
        """Execute the Django management command."""
        from django.core.management import call_command

        merged_kwargs = {**self.kwargs, **context.kwargs}
        # Convert kwargs to command-line args
        args = []
        for key, value in merged_kwargs.items():
            args.append(f"--{key}")
            if value is not True:  # Skip boolean flags
                args.append(str(value))

        call_command(self._target, *args)
        return {"command": self._target, "args": args}

    async def execute_async(self, context: JobContext) -> Any:
        """Execute management command in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, context)