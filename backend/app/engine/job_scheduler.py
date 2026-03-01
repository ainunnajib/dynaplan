import uuid
from typing import Any, Dict, List, Optional

from app.engine.job_executor import AsyncJobExecutor, JobHandler
from app.engine.job_registry import JobRecord

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without APScheduler
    AsyncIOScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]
    APSCHEDULER_AVAILABLE = False


def apscheduler_available() -> bool:
    return APSCHEDULER_AVAILABLE


class JobScheduler:
    """APScheduler wrapper that submits cron-triggered jobs into AsyncJobExecutor."""

    def __init__(
        self,
        executor: AsyncJobExecutor,
        timezone: str = "UTC",
    ) -> None:
        self.executor = executor
        self.timezone = timezone
        self._definitions: Dict[str, Dict[str, Any]] = {}
        self._scheduler = (
            AsyncIOScheduler(timezone=timezone) if APSCHEDULER_AVAILABLE else None
        )

    @property
    def is_running(self) -> bool:
        if self._scheduler is None:
            return False
        return bool(self._scheduler.running)

    def start(self) -> None:
        scheduler = self._require_scheduler()
        if not scheduler.running:
            scheduler.start()

    async def shutdown(self, wait: bool = True) -> None:
        scheduler = self._require_scheduler()
        if scheduler.running:
            scheduler.shutdown(wait=wait)

    def add_cron_job(
        self,
        name: str,
        cron_expression: str,
        handler: JobHandler,
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 0,
        retry_backoff_seconds: float = 1.0,
        retry_backoff_multiplier: float = 2.0,
        timeout_seconds: Optional[float] = None,
        schedule_id: Optional[str] = None,
        replace_existing: bool = True,
    ) -> str:
        scheduler = self._require_scheduler()
        trigger = CronTrigger.from_crontab(cron_expression, timezone=self.timezone)
        resolved_id = schedule_id or uuid.uuid4().hex

        self._definitions[resolved_id] = {
            "name": name,
            "handler": handler,
            "payload": payload or {},
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
            "retry_backoff_multiplier": retry_backoff_multiplier,
            "timeout_seconds": timeout_seconds,
            "cron_expression": cron_expression,
        }

        scheduler.add_job(
            self._run_scheduled_job,
            trigger=trigger,
            id=resolved_id,
            name=name,
            replace_existing=replace_existing,
            coalesce=True,
            max_instances=1,
            kwargs={"schedule_id": resolved_id},
        )
        return resolved_id

    def remove_job(self, schedule_id: str) -> None:
        scheduler = self._require_scheduler()
        scheduler.remove_job(schedule_id)
        self._definitions.pop(schedule_id, None)

    def pause_job(self, schedule_id: str) -> None:
        scheduler = self._require_scheduler()
        scheduler.pause_job(schedule_id)

    def resume_job(self, schedule_id: str) -> None:
        scheduler = self._require_scheduler()
        scheduler.resume_job(schedule_id)

    def list_schedule_ids(self) -> List[str]:
        scheduler = self._require_scheduler()
        return [job.id for job in scheduler.get_jobs()]

    async def trigger_now(self, schedule_id: str) -> JobRecord:
        definition = self._definitions.get(schedule_id)
        if definition is None:
            raise ValueError("Scheduled job not found")
        return await self.executor.submit(
            name=definition["name"],
            handler=definition["handler"],
            payload=definition["payload"],
            max_retries=definition["max_retries"],
            retry_backoff_seconds=definition["retry_backoff_seconds"],
            retry_backoff_multiplier=definition["retry_backoff_multiplier"],
            timeout_seconds=definition["timeout_seconds"],
        )

    async def _run_scheduled_job(self, schedule_id: str) -> None:
        definition = self._definitions.get(schedule_id)
        if definition is None:
            return
        await self.executor.submit(
            name=definition["name"],
            handler=definition["handler"],
            payload=definition["payload"],
            max_retries=definition["max_retries"],
            retry_backoff_seconds=definition["retry_backoff_seconds"],
            retry_backoff_multiplier=definition["retry_backoff_multiplier"],
            timeout_seconds=definition["timeout_seconds"],
        )

    def _require_scheduler(self):
        if self._scheduler is None:
            raise RuntimeError(
                "APScheduler is not installed. Install APScheduler to enable cron scheduling."
            )
        return self._scheduler
