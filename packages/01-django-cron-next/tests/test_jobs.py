"""
Tests for job classes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from django_cron_next.jobs import CronJob, AsyncCronJob, ManagementCommandJob, JobContext


class TestCronJob:
    """Tests for synchronous CronJob."""

    def test_cron_job_creation(self):
        """Test creating a basic CronJob."""
        job = CronJob(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.my_function",
        )
        assert job.name == "test_job"
        assert job.schedule == "0 2 * * *"
        assert job.target == "my_module.my_function"
        assert job.enabled is True
        assert job.timezone == "UTC"

    def test_cron_job_with_kwargs(self):
        """Test CronJob with custom kwargs."""
        job = CronJob(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.my_function",
            kwargs={"arg1": "value1", "arg2": 42},
        )
        assert job.kwargs == {"arg1": "value1", "arg2": 42}

    def test_cron_job_validation(self):
        """Test job validation."""
        job = CronJob(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.my_function",
        )
        assert job.validate() is True

        # Invalid job - missing target
        job2 = CronJob(name="test", schedule="0 2 * * *", target="")
        assert job2.validate() is False

    @patch("django_cron_next.jobs.importlib.import_module")
    def test_execute_sync_function(self, mock_import):
        """Test executing a synchronous function."""
        mock_func = MagicMock(return_value="success")
        mock_module = MagicMock()
        mock_module.my_function = mock_func
        mock_import.return_value = mock_module

        job = CronJob(
            name="test_job",
            schedule="0 2 * * *",
            target="my_module.my_function",
        )

        context = JobContext(
            job_name="test_job",
            run_id="test-run-id",
            started_at=0.0,
            kwargs={"extra": "kwarg"},
        )

        result = job.execute(context)
        assert result == "success"
        mock_func.assert_called_once_with(extra="kwarg")


class TestAsyncCronJob:
    """Tests for asynchronous AsyncCronJob."""

    @pytest.mark.asyncio
    @patch("django_cron_next.jobs.importlib.import_module")
    async def test_execute_async_function(self, mock_import):
        """Test executing an async function."""
        async def async_func(**kwargs):
            return f"async result: {kwargs.get('extra')}"

        mock_module = MagicMock()
        mock_module.my_async_function = async_func
        mock_import.return_value = mock_module

        job = AsyncCronJob(
            name="test_async_job",
            schedule="0 2 * * *",
            target="my_module.my_async_function",
        )

        context = JobContext(
            job_name="test_async_job",
            run_id="test-run-id",
            started_at=0.0,
            kwargs={"extra": "value"},
        )

        result = await job.execute_async(context)
        assert result == "async result: value"

    @pytest.mark.asyncio
    @patch("django_cron_next.jobs.importlib.import_module")
    async def test_execute_sync_function_in_async(self, mock_import):
        """Test executing sync function via async executor."""
        def sync_func(**kwargs):
            return f"sync result: {kwargs.get('extra')}"

        mock_module = MagicMock()
        mock_module.my_sync_function = sync_func
        mock_import.return_value = mock_module

        job = AsyncCronJob(
            name="test_async_job",
            schedule="0 2 * * *",
            target="my_module.my_sync_function",
        )

        context = JobContext(
            job_name="test_async_job",
            run_id="test-run-id",
            started_at=0.0,
            kwargs={"extra": "value"},
        )

        result = await job.execute_async(context)
        assert result == "sync result: value"


class TestManagementCommandJob:
    """Tests for ManagementCommandJob."""

    @patch("django_cron_next.jobs.call_command")
    def test_execute_management_command(self, mock_call_command):
        """Test executing a Django management command."""
        job = ManagementCommandJob(
            name="test_cmd_job",
            schedule="0 2 * * *",
            target="migrate",
            kwargs={"plan": True, "verbosity": 0},
        )

        context = JobContext(
            job_name="test_cmd_job",
            run_id="test-run-id",
            started_at=0.0,
        )

        result = job.execute(context)
        assert result["command"] == "migrate"
        mock_call_command.assert_called_once_with("migrate", "--plan", "--verbosity", "0")

    @pytest.mark.asyncio
    @patch("django_cron_next.jobs.call_command")
    async def test_execute_async_management_command(self, mock_call_command):
        """Test executing management command asynchronously."""
        job = ManagementCommandJob(
            name="test_cmd_job",
            schedule="0 2 * * *",
            target="collectstatic",
            kwargs={"noinput": True},
        )

        context = JobContext(
            job_name="test_cmd_job",
            run_id="test-run-id",
            started_at=0.0,
        )

        result = await job.execute_async(context)
        assert result["command"] == "collectstatic"