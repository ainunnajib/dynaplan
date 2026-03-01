import asyncio
import uuid

import pytest

from app.engine.job_executor import AsyncJobExecutor
from app.engine.job_registry import JobState
from app.engine.job_scheduler import JobScheduler, apscheduler_available


@pytest.mark.asyncio
async def test_executor_completes_job_and_persists_result():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def handler(job):
            return job.payload["value"] * 2

        job = await executor.submit(
            name="double",
            handler=handler,
            payload={"value": 21},
        )
        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.completed
        assert finished.result == 42
        assert finished.attempts == 1
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_executor_records_state_machine_history():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def handler(_job):
            await asyncio.sleep(0)
            return "ok"

        job = await executor.submit(name="history", handler=handler)
        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state_history == [
            JobState.pending,
            JobState.queued,
            JobState.running,
            JobState.completed,
        ]
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_retry_with_backoff_eventually_completes():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    attempts = {"count": 0}
    try:
        async def flaky(_job):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient error")
            return "done"

        job = await executor.submit(
            name="retry-success",
            handler=flaky,
            max_retries=2,
            retry_backoff_seconds=0.01,
        )
        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.completed
        assert finished.attempts == 2
        assert JobState.retrying in finished.state_history
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_retry_exhaustion_moves_job_to_dead_letter():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def always_fail(_job):
            raise RuntimeError("permanent failure")

        job = await executor.submit(
            name="retry-fail",
            handler=always_fail,
            max_retries=1,
            retry_backoff_seconds=0.01,
        )
        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.failed
        assert finished.attempts == 2
        assert len(executor.get_dead_letters()) == 1
        assert executor.get_dead_letters()[0].id == job.id
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_retry_sets_next_retry_timestamp():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def always_fail(_job):
            raise RuntimeError("boom")

        job = await executor.submit(
            name="retry-timestamp",
            handler=always_fail,
            max_retries=1,
            retry_backoff_seconds=0.05,
            retry_backoff_multiplier=2.0,
        )
        deadline = asyncio.get_running_loop().time() + 1.0
        retrying_snapshot = None
        while asyncio.get_running_loop().time() < deadline:
            current = await executor.get_job(job.id)
            if current is not None and current.state == JobState.retrying:
                retrying_snapshot = current
                break
            await asyncio.sleep(0.01)

        assert retrying_snapshot is not None
        assert retrying_snapshot.next_retry_at is not None
        assert retrying_snapshot.last_error == "boom"

        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.failed
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_cancel_queued_job():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    started = asyncio.Event()
    release = asyncio.Event()
    try:
        async def blocking(_job):
            started.set()
            await release.wait()
            return "done"

        async def quick(_job):
            return "quick"

        running_job = await executor.submit(name="blocker", handler=blocking)
        await started.wait()
        queued_job = await executor.submit(name="queued", handler=quick)

        cancelled = await executor.cancel(queued_job.id)
        assert cancelled is True

        release.set()
        await executor.wait_for_job(running_job.id, timeout_seconds=1.0)
        finished = await executor.wait_for_job(queued_job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.cancelled
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_cancel_running_job():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def long_running(_job):
            await asyncio.sleep(10)
            return "never"

        job = await executor.submit(name="cancel-running", handler=long_running)

        async def is_running():
            current = await executor.get_job(job.id)
            return current is not None and current.state == JobState.running

        deadline = asyncio.get_running_loop().time() + 1.0
        while asyncio.get_running_loop().time() < deadline:
            if await is_running():
                break
            await asyncio.sleep(0.01)

        cancelled = await executor.cancel(job.id)
        assert cancelled is True

        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.cancelled
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_timeout_enforcement_marks_failed():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def too_slow(_job):
            await asyncio.sleep(0.2)
            return "late"

        job = await executor.submit(
            name="timeout",
            handler=too_slow,
            max_retries=0,
            timeout_seconds=0.05,
        )
        finished = await executor.wait_for_job(job.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.failed
        assert "timed out" in (finished.last_error or "").lower()
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_wait_for_missing_job_returns_none():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        result = await executor.wait_for_job(uuid.uuid4(), timeout_seconds=0.1)
        assert result is None
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_list_jobs_can_filter_by_state():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    try:
        async def success(_job):
            return "ok"

        async def fail(_job):
            raise RuntimeError("x")

        completed = await executor.submit(name="done", handler=success)
        failed = await executor.submit(name="bad", handler=fail)
        await executor.wait_for_job(completed.id, timeout_seconds=1.0)
        await executor.wait_for_job(failed.id, timeout_seconds=1.0)

        failed_only = await executor.list_jobs(states=[JobState.failed])
        assert len(failed_only) == 1
        assert failed_only[0].id == failed.id
    finally:
        await executor.stop()


@pytest.mark.asyncio
async def test_submit_requires_running_executor():
    executor = AsyncJobExecutor(worker_count=1)

    async def handler(_job):
        return "noop"

    with pytest.raises(RuntimeError):
        await executor.submit(name="must-fail", handler=handler)


@pytest.mark.asyncio
async def test_stop_without_drain_cancels_running_and_queued_jobs():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    started = asyncio.Event()
    try:
        async def blocker(_job):
            started.set()
            await asyncio.sleep(10)
            return "done"

        async def quick(_job):
            return "quick"

        running_job = await executor.submit(name="running", handler=blocker)
        await started.wait()
        queued_job = await executor.submit(name="queued", handler=quick)

        await executor.stop(drain=False, timeout_seconds=0.1)

        running = await executor.get_job(running_job.id)
        queued = await executor.get_job(queued_job.id)
        assert running is not None
        assert queued is not None
        assert running.state == JobState.cancelled
        assert queued.state == JobState.cancelled
    finally:
        if executor.is_running:
            await executor.stop()


def test_scheduler_requires_apscheduler_if_missing():
    if apscheduler_available():
        pytest.skip("APScheduler installed in this environment")

    scheduler = JobScheduler(executor=AsyncJobExecutor(worker_count=1))
    with pytest.raises(RuntimeError, match="APScheduler"):
        scheduler.start()


@pytest.mark.asyncio
@pytest.mark.skipif(not apscheduler_available(), reason="APScheduler is not installed")
async def test_scheduler_can_register_trigger_and_remove_cron_job():
    executor = AsyncJobExecutor(worker_count=1)
    await executor.start()
    scheduler = JobScheduler(executor=executor)
    scheduler.start()
    try:
        async def handler(_job):
            return "ok"

        schedule_id = scheduler.add_cron_job(
            name="every-minute",
            cron_expression="*/1 * * * *",
            handler=handler,
        )
        assert schedule_id in scheduler.list_schedule_ids()

        triggered = await scheduler.trigger_now(schedule_id)
        finished = await executor.wait_for_job(triggered.id, timeout_seconds=1.0)
        assert finished is not None
        assert finished.state == JobState.completed

        scheduler.remove_job(schedule_id)
        assert schedule_id not in scheduler.list_schedule_ids()
    finally:
        await scheduler.shutdown()
        await executor.stop()
