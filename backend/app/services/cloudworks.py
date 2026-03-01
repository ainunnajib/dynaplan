import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloudworks import (
    CloudWorksConnection,
    CloudWorksRun,
    CloudWorksSchedule,
    RunStatus,
)
from app.schemas.cloudworks import (
    ConnectionCreate,
    ConnectionUpdate,
    ScheduleCreate,
    ScheduleUpdate,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection CRUD
# ---------------------------------------------------------------------------

async def create_connection(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ConnectionCreate,
) -> CloudWorksConnection:
    conn = CloudWorksConnection(
        name=data.name,
        model_id=model_id,
        connector_type=data.connector_type,
        config=data.config or {},
        is_active=data.is_active if data.is_active is not None else True,
        created_by=user_id,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def get_connection_by_id(
    db: AsyncSession,
    conn_id: uuid.UUID,
) -> Optional[CloudWorksConnection]:
    result = await db.execute(
        select(CloudWorksConnection).where(CloudWorksConnection.id == conn_id)
    )
    return result.scalar_one_or_none()


async def list_connections_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[CloudWorksConnection]:
    result = await db.execute(
        select(CloudWorksConnection)
        .where(CloudWorksConnection.model_id == model_id)
        .order_by(CloudWorksConnection.created_at.asc())
    )
    return list(result.scalars().all())


async def update_connection(
    db: AsyncSession,
    conn: CloudWorksConnection,
    data: ConnectionUpdate,
) -> CloudWorksConnection:
    if data.name is not None:
        conn.name = data.name
    if data.connector_type is not None:
        conn.connector_type = data.connector_type
    if data.config is not None:
        conn.config = data.config
    if data.is_active is not None:
        conn.is_active = data.is_active
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def delete_connection(db: AsyncSession, conn: CloudWorksConnection) -> None:
    await db.delete(conn)
    await db.commit()


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------

async def create_schedule(
    db: AsyncSession,
    connection_id: uuid.UUID,
    data: ScheduleCreate,
) -> CloudWorksSchedule:
    schedule = CloudWorksSchedule(
        connection_id=connection_id,
        name=data.name,
        description=data.description,
        schedule_type=data.schedule_type,
        cron_expression=data.cron_expression,
        source_config=data.source_config or {},
        target_config=data.target_config or {},
        is_enabled=data.is_enabled if data.is_enabled is not None else True,
        max_retries=data.max_retries if data.max_retries is not None else 3,
        retry_delay_seconds=data.retry_delay_seconds if data.retry_delay_seconds is not None else 60,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def get_schedule_by_id(
    db: AsyncSession,
    schedule_id: uuid.UUID,
) -> Optional[CloudWorksSchedule]:
    result = await db.execute(
        select(CloudWorksSchedule).where(CloudWorksSchedule.id == schedule_id)
    )
    return result.scalar_one_or_none()


async def list_schedules_for_connection(
    db: AsyncSession,
    connection_id: uuid.UUID,
) -> List[CloudWorksSchedule]:
    result = await db.execute(
        select(CloudWorksSchedule)
        .where(CloudWorksSchedule.connection_id == connection_id)
        .order_by(CloudWorksSchedule.created_at.asc())
    )
    return list(result.scalars().all())


async def update_schedule(
    db: AsyncSession,
    schedule: CloudWorksSchedule,
    data: ScheduleUpdate,
) -> CloudWorksSchedule:
    if data.name is not None:
        schedule.name = data.name
    if data.description is not None:
        schedule.description = data.description
    if data.schedule_type is not None:
        schedule.schedule_type = data.schedule_type
    if data.cron_expression is not None:
        schedule.cron_expression = data.cron_expression
    if data.source_config is not None:
        schedule.source_config = data.source_config
    if data.target_config is not None:
        schedule.target_config = data.target_config
    if data.max_retries is not None:
        schedule.max_retries = data.max_retries
    if data.retry_delay_seconds is not None:
        schedule.retry_delay_seconds = data.retry_delay_seconds
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def delete_schedule(db: AsyncSession, schedule: CloudWorksSchedule) -> None:
    await db.delete(schedule)
    await db.commit()


async def enable_disable_schedule(
    db: AsyncSession,
    schedule: CloudWorksSchedule,
    is_enabled: bool,
) -> CloudWorksSchedule:
    schedule.is_enabled = is_enabled
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


# ---------------------------------------------------------------------------
# Run management
# ---------------------------------------------------------------------------

async def trigger_run(
    db: AsyncSession,
    schedule_id: uuid.UUID,
) -> CloudWorksRun:
    run = CloudWorksRun(
        schedule_id=schedule_id,
        status=RunStatus.pending,
        attempt_number=1,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def get_run_by_id(
    db: AsyncSession,
    run_id: uuid.UUID,
) -> Optional[CloudWorksRun]:
    result = await db.execute(
        select(CloudWorksRun).where(CloudWorksRun.id == run_id)
    )
    return result.scalar_one_or_none()


async def list_runs_for_schedule(
    db: AsyncSession,
    schedule_id: uuid.UUID,
) -> List[CloudWorksRun]:
    result = await db.execute(
        select(CloudWorksRun)
        .where(CloudWorksRun.schedule_id == schedule_id)
        .order_by(CloudWorksRun.created_at.desc())
    )
    return list(result.scalars().all())


async def mark_run_running(
    db: AsyncSession,
    run: CloudWorksRun,
) -> CloudWorksRun:
    run.status = RunStatus.running
    run.started_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def mark_run_completed(
    db: AsyncSession,
    run: CloudWorksRun,
    records_processed: Optional[int] = None,
) -> CloudWorksRun:
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    if records_processed is not None:
        run.records_processed = records_processed
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def mark_run_failed(
    db: AsyncSession,
    run: CloudWorksRun,
    error_message: Optional[str] = None,
) -> CloudWorksRun:
    run.status = RunStatus.failed
    run.completed_at = datetime.now(timezone.utc)
    if error_message is not None:
        run.error_message = error_message
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def retry_run(
    db: AsyncSession,
    run: CloudWorksRun,
) -> CloudWorksRun:
    """Retry a failed run if under max_retries limit."""
    schedule = await get_schedule_by_id(db, run.schedule_id)
    if schedule is None:
        raise ValueError("Schedule not found")

    if run.attempt_number >= schedule.max_retries:
        raise ValueError(
            f"Max retries ({schedule.max_retries}) exceeded for run {run.id}"
        )

    # Create a new run with incremented attempt number
    new_run = CloudWorksRun(
        schedule_id=run.schedule_id,
        status=RunStatus.retrying,
        attempt_number=run.attempt_number + 1,
    )
    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)
    return new_run
