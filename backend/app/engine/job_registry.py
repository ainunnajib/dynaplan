import asyncio
import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobState(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    retrying = "retrying"
    cancelled = "cancelled"


TERMINAL_JOB_STATES = {
    JobState.completed,
    JobState.failed,
    JobState.cancelled,
}


ALLOWED_TRANSITIONS = {
    JobState.pending: {JobState.queued, JobState.cancelled},
    JobState.queued: {JobState.running, JobState.cancelled},
    JobState.running: {
        JobState.completed,
        JobState.failed,
        JobState.retrying,
        JobState.cancelled,
    },
    JobState.retrying: {JobState.queued, JobState.cancelled},
    JobState.completed: set(),
    JobState.failed: set(),
    JobState.cancelled: set(),
}


@dataclass
class JobRecord:
    id: uuid.UUID
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    state: JobState = JobState.pending
    attempts: int = 0
    max_retries: int = 0
    retry_backoff_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    timeout_seconds: Optional[float] = None
    result: Optional[Any] = None
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    cancel_requested: bool = False
    state_history: List[JobState] = field(default_factory=list)
    done_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def retries_used(self) -> int:
        return max(self.attempts - 1, 0)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES


class JobRegistry:
    """Track submitted jobs, active worker tasks, and legal state transitions."""

    def __init__(self) -> None:
        self._jobs: Dict[uuid.UUID, JobRecord] = {}
        self._active_tasks: Dict[uuid.UUID, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, job: JobRecord) -> JobRecord:
        async with self._lock:
            if job.id in self._jobs:
                raise ValueError("Job already exists in registry")
            if len(job.state_history) == 0:
                job.state_history = [job.state]
            self._jobs[job.id] = job
            return job

    async def get(self, job_id: uuid.UUID) -> Optional[JobRecord]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list_jobs(self, states: Optional[List[JobState]] = None) -> List[JobRecord]:
        async with self._lock:
            jobs = list(self._jobs.values())
            if states is not None:
                allowed = set(states)
                jobs = [job for job in jobs if job.state in allowed]
            jobs.sort(key=lambda item: item.created_at)
            return jobs

    async def transition(
        self,
        job_id: uuid.UUID,
        new_state: JobState,
        error: Optional[str] = None,
        next_retry_delay_seconds: Optional[float] = None,
    ) -> JobRecord:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError("Job not found in registry")
            self._apply_transition(job, new_state, error, next_retry_delay_seconds)
            return job

    async def set_result(self, job_id: uuid.UUID, result: Any) -> Optional[JobRecord]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.result = result
            return job

    async def bind_task(self, job_id: uuid.UUID, task: asyncio.Task) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.is_terminal:
                return
            self._active_tasks[job_id] = task

    async def unbind_task(self, job_id: uuid.UUID) -> None:
        async with self._lock:
            self._active_tasks.pop(job_id, None)

    async def active_job_ids(self) -> List[uuid.UUID]:
        async with self._lock:
            return list(self._active_tasks.keys())

    async def request_cancel(self, job_id: uuid.UUID) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.is_terminal:
                return False

            job.cancel_requested = True
            task = self._active_tasks.get(job_id)
            if task is not None:
                task.cancel()
                return True

            self._apply_transition(job, JobState.cancelled)
            return True

    def _apply_transition(
        self,
        job: JobRecord,
        new_state: JobState,
        error: Optional[str] = None,
        next_retry_delay_seconds: Optional[float] = None,
    ) -> None:
        if new_state == job.state:
            if error is not None:
                job.last_error = error
            return

        allowed = ALLOWED_TRANSITIONS.get(job.state, set())
        if new_state not in allowed:
            raise ValueError(
                "Invalid job state transition: %s -> %s"
                % (job.state.value, new_state.value)
            )

        now = _utcnow()
        job.state = new_state
        job.state_history.append(new_state)

        if error is not None:
            job.last_error = error

        if new_state == JobState.queued:
            job.queued_at = now
            job.next_retry_at = None
        elif new_state == JobState.running:
            job.started_at = now
            job.attempts += 1
        elif new_state == JobState.retrying:
            delay = next_retry_delay_seconds if next_retry_delay_seconds is not None else 0
            job.next_retry_at = now + timedelta(seconds=delay)
        elif new_state in TERMINAL_JOB_STATES:
            job.finished_at = now
            job.done_event.set()
            self._active_tasks.pop(job.id, None)
