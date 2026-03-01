import asyncio
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from app.engine.job_registry import JobRecord, JobRegistry, JobState

JobHandler = Callable[[JobRecord], Awaitable[Any]]
STOP_TOKEN = object()


class AsyncJobExecutor:
    """
    Async background executor using an asyncio.Queue + worker pool.

    Job lifecycle:
      pending -> queued -> running -> completed
                                  -> retrying -> queued ...
                                  -> failed
                                  -> cancelled
    """

    def __init__(
        self,
        worker_count: int = 2,
        queue_maxsize: int = 0,
        registry: Optional[JobRegistry] = None,
    ) -> None:
        if worker_count <= 0:
            raise ValueError("worker_count must be > 0")

        self.worker_count = worker_count
        self.registry = registry or JobRegistry()

        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_maxsize)
        self._workers: List[asyncio.Task] = []
        self._retry_tasks: Set[asyncio.Task] = set()
        self._handlers: Dict[uuid.UUID, JobHandler] = {}

        self._running = False
        self._lifecycle_lock = asyncio.Lock()

        self._dead_letter_queue: asyncio.Queue = asyncio.Queue()
        self._dead_letters: List[JobRecord] = []

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._running:
                return

            self._running = True
            self._workers = [
                asyncio.create_task(
                    self._worker_loop(index),
                    name="dynaplan-job-worker-%s" % index,
                )
                for index in range(self.worker_count)
            ]

    async def stop(
        self,
        drain: bool = True,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        async with self._lifecycle_lock:
            if not self._running:
                return

            if not drain:
                await self._cancel_running_jobs()
                await self._cancel_queued_jobs()

            for retry_task in list(self._retry_tasks):
                retry_task.cancel()

            retry_tasks = list(self._retry_tasks)
            self._retry_tasks.clear()

            if drain:
                await self._wait_for_queue(timeout_seconds)

            self._running = False

            workers = list(self._workers)
            self._workers = []
            for _ in workers:
                await self._queue.put(STOP_TOKEN)

        await asyncio.gather(*workers, return_exceptions=True)
        if len(retry_tasks) > 0:
            await asyncio.gather(*retry_tasks, return_exceptions=True)

    async def submit(
        self,
        name: str,
        handler: JobHandler,
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 0,
        retry_backoff_seconds: float = 1.0,
        retry_backoff_multiplier: float = 2.0,
        timeout_seconds: Optional[float] = None,
        job_id: Optional[uuid.UUID] = None,
    ) -> JobRecord:
        if not self._running:
            raise RuntimeError("Executor is not running")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be >= 0")
        if retry_backoff_multiplier < 1:
            raise ValueError("retry_backoff_multiplier must be >= 1")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        record = JobRecord(
            id=job_id or uuid.uuid4(),
            name=name,
            payload=payload or {},
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            retry_backoff_multiplier=retry_backoff_multiplier,
            timeout_seconds=timeout_seconds,
        )
        await self.registry.register(record)

        self._handlers[record.id] = handler
        await self.registry.transition(record.id, JobState.queued)
        await self._queue.put(record.id)
        return record

    async def cancel(self, job_id: uuid.UUID) -> bool:
        return await self.registry.request_cancel(job_id)

    async def get_job(self, job_id: uuid.UUID) -> Optional[JobRecord]:
        return await self.registry.get(job_id)

    async def list_jobs(self, states: Optional[List[JobState]] = None) -> List[JobRecord]:
        return await self.registry.list_jobs(states=states)

    async def wait_for_job(
        self,
        job_id: uuid.UUID,
        timeout_seconds: Optional[float] = None,
    ) -> Optional[JobRecord]:
        job = await self.registry.get(job_id)
        if job is None:
            return None

        waiter = job.done_event.wait()
        if timeout_seconds is None:
            await waiter
        else:
            await asyncio.wait_for(waiter, timeout=timeout_seconds)
        return await self.registry.get(job_id)

    async def next_dead_letter(
        self,
        timeout_seconds: Optional[float] = None,
    ) -> Optional[JobRecord]:
        if timeout_seconds is None:
            return await self._dead_letter_queue.get()
        return await asyncio.wait_for(
            self._dead_letter_queue.get(),
            timeout=timeout_seconds,
        )

    def get_dead_letters(self) -> List[JobRecord]:
        return list(self._dead_letters)

    async def _worker_loop(self, worker_index: int) -> None:
        while True:
            queue_item = await self._queue.get()
            try:
                if queue_item is STOP_TOKEN:
                    return

                job_id = queue_item
                job = await self.registry.get(job_id)
                if job is None:
                    continue
                if job.state == JobState.cancelled or job.cancel_requested:
                    await self._finalize_cancelled(job_id)
                    continue
                if job.state != JobState.queued:
                    continue

                await self.registry.transition(job_id, JobState.running)
                run_task = asyncio.create_task(
                    self._execute_job(job_id),
                    name="dynaplan-job-runner-%s-%s" % (worker_index, job_id),
                )
                await self.registry.bind_task(job_id, run_task)
                await run_task
            finally:
                self._queue.task_done()

    async def _execute_job(self, job_id: uuid.UUID) -> None:
        job = await self.registry.get(job_id)
        if job is None:
            return

        handler = self._handlers.get(job_id)
        if handler is None:
            await self._fail_without_retry(job_id, "Job handler was not found")
            return

        if job.cancel_requested:
            await self._finalize_cancelled(job_id)
            return

        try:
            if job.timeout_seconds is not None:
                result = await asyncio.wait_for(
                    handler(job),
                    timeout=job.timeout_seconds,
                )
            else:
                result = await handler(job)
        except asyncio.CancelledError:
            await self._finalize_cancelled(job_id)
            return
        except asyncio.TimeoutError:
            await self._handle_failure(
                job_id,
                "Job timed out after %s seconds" % job.timeout_seconds,
            )
            return
        except Exception as exc:  # noqa: BLE001
            await self._handle_failure(job_id, str(exc))
            return

        await self.registry.set_result(job_id, result)
        await self.registry.transition(job_id, JobState.completed)
        self._handlers.pop(job_id, None)

    async def _handle_failure(self, job_id: uuid.UUID, error: str) -> None:
        job = await self.registry.get(job_id)
        if job is None:
            return
        if job.cancel_requested:
            await self._finalize_cancelled(job_id)
            return

        retries_used = job.retries_used
        if retries_used < job.max_retries:
            delay = self._compute_retry_delay(
                base_seconds=job.retry_backoff_seconds,
                multiplier=job.retry_backoff_multiplier,
                retry_index=retries_used,
            )
            try:
                await self.registry.transition(
                    job_id,
                    JobState.retrying,
                    error=error,
                    next_retry_delay_seconds=delay,
                )
            except ValueError:
                # Another task may have transitioned the job to terminal state.
                return

            retry_task = asyncio.create_task(
                self._enqueue_retry(job_id, delay),
                name="dynaplan-job-retry-%s" % job_id,
            )
            self._retry_tasks.add(retry_task)
            retry_task.add_done_callback(self._retry_tasks.discard)
            return

        await self._fail_without_retry(job_id, error)

    async def _fail_without_retry(self, job_id: uuid.UUID, error: str) -> None:
        try:
            await self.registry.transition(job_id, JobState.failed, error=error)
        except ValueError:
            return

        job = await self.registry.get(job_id)
        if job is not None:
            self._dead_letters.append(job)
            await self._dead_letter_queue.put(job)

        self._handlers.pop(job_id, None)

    async def _finalize_cancelled(self, job_id: uuid.UUID) -> None:
        job = await self.registry.get(job_id)
        if job is None:
            return
        if job.is_terminal:
            self._handlers.pop(job_id, None)
            return

        try:
            await self.registry.transition(job_id, JobState.cancelled)
        except ValueError:
            pass
        self._handlers.pop(job_id, None)

    async def _enqueue_retry(self, job_id: uuid.UUID, delay_seconds: float) -> None:
        try:
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            return

        job = await self.registry.get(job_id)
        if job is None:
            return
        if job.cancel_requested or job.state == JobState.cancelled:
            await self._finalize_cancelled(job_id)
            return
        if job.state != JobState.retrying:
            return
        if not self._running:
            await self._finalize_cancelled(job_id)
            return

        try:
            await self.registry.transition(job_id, JobState.queued)
        except ValueError:
            return
        await self._queue.put(job_id)

    async def _wait_for_queue(self, timeout_seconds: Optional[float]) -> None:
        waiter = self._queue.join()
        if timeout_seconds is None:
            await waiter
        else:
            try:
                await asyncio.wait_for(waiter, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                return

    async def _cancel_running_jobs(self) -> None:
        active_ids = await self.registry.active_job_ids()
        for job_id in active_ids:
            await self.registry.request_cancel(job_id)

    async def _cancel_queued_jobs(self) -> None:
        while True:
            try:
                queue_item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            if queue_item is not STOP_TOKEN:
                await self.registry.request_cancel(queue_item)
            self._queue.task_done()

    @staticmethod
    def _compute_retry_delay(
        base_seconds: float,
        multiplier: float,
        retry_index: int,
    ) -> float:
        return max(base_seconds * (multiplier ** retry_index), 0.0)
