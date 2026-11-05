"""
Tests for the CronScheduler.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from django_cron_next.scheduler import CronScheduler


class TestCronScheduler:
    """Tests for CronScheduler."""

    @pytest.fixture
    def scheduler(self):
        """Create a scheduler with mocked backend."""
        with patch("django_cron_next.scheduler.get_backend") as mock_get_backend:
            mock_backend = AsyncMock()
            mock_get_backend.return_value = mock_backend
            scheduler = CronScheduler(backend="database")
            scheduler.backend = mock_backend
            yield scheduler

    def test_scheduler_creation(self, scheduler):
        """Test creating a scheduler."""
        assert scheduler is not None
        assert scheduler.backend is not None
        assert scheduler._jobs == {}
        assert scheduler._running is False

    def test_add_job_function(self, scheduler):
        """Adding a synchronous function job."""
        job = scheduler.add_job(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.my_function",
            job_type="function",
        )
        assert job.name == "test_job"
        assert "test_job" in scheduler._jobs

    def test_add_job_async_function(self, scheduler):
        """Adding an async function job."""
        job = scheduler.add_job(
            name="async_job",
            schedule="0 3 * * *",
            target="my_module.async_func",
            job_type="async_function",
        )
        assert job.name == "async_job"
        assert "async_job" in scheduler._jobs

    def test_add_job_management_command(self, scheduler):
        """Adding a management command job."""
        job = scheduler.add_job(
            name="cmd_job",
            schedule="0 4 * * *",
            target="migrate",
            job_type="management_command",
        )
        assert job.name == "cmd_job"
        assert "cmd_job" in scheduler._jobs

    def test_remove_job(self, scheduler):
        """Removing a job."""
        scheduler.add_job(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.func",
        )
        assert scheduler.remove_job("test_job") is True
        assert "test_job" not in scheduler._jobs
        assert scheduler.remove_job("nonexistent") is False

    def test_get_job(self, scheduler):
        """Getting a job by name."""
        scheduler.add_job(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.func",
        )
        job = scheduler.get_job("test_job")
        assert job is not None
        assert job.name == "test_job"
        assert scheduler.get_job("nonexistent") is None

    def test_list_jobs(self, scheduler):
        """Listing all jobs."""
        scheduler.add_job(name="job1", schedule="0 1 * * *", target="mod.func1")
        scheduler.add_job(name="job2", schedule="0 2 * * *", target="mod.func2")
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2
        names = {j.name for j in jobs}
        assert names == {"job1", "job2"}

    @pytest.mark.asyncio
    async def test_run_job_now(self, scheduler):
        """Running a job immediately."""
        scheduler.add_job(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.func",
        )
        scheduler.backend.enqueue_job = AsyncMock(return_value="run-123")

        run_id = await scheduler.run_job_now("test_job")
        assert run_id == "run-123"
        scheduler.backend.enqueue_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_job_now_not_found(self, scheduler):
        """Running a non-existent job."""
        with pytest.raises(ValueError, match="Job not found"):
            await scheduler.run_job_now("nonexistent")

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        """Starting and stopping the scheduler."""
        assert scheduler._running is False
        await scheduler.start()
        assert scheduler._running is True
        scheduler.backend.start.assert_called_once()
        await scheduler.stop()
        assert scheduler._running is False
        scheduler.backend.stop.assert_called_once()

    def test_get_next_run(self, scheduler):
        """Calculating next run time."""
        next_run = scheduler._get_next_run("0 2 * * *", "UTC")
        assert next_run is not None
        assert next_run.hour == 2
        assert next_run.minute == 0