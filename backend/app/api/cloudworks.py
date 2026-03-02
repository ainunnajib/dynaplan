import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.cloudworks import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionUpdate,
    RunCompleteRequest,
    RunFailRequest,
    RunResponse,
    RunTriggerResponse,
    ScheduleCreate,
    ScheduleEnableRequest,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.services.cloudworks import (
    create_connection,
    create_schedule,
    delete_connection,
    delete_schedule,
    enable_disable_schedule,
    execute_run,
    get_connection_by_id,
    get_run_by_id,
    get_schedule_by_id,
    list_connections_for_model,
    list_runs_for_schedule,
    list_schedules_for_connection,
    mark_run_completed,
    mark_run_failed,
    retry_run,
    trigger_run,
    update_connection,
    update_schedule,
)

router = APIRouter(tags=["cloudworks"])


def _conn_or_404(conn):
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    return conn


def _schedule_or_404(schedule):
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )
    return schedule


def _run_or_404(run):
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return run


# ---------------------------------------------------------------------------
# Connection routes
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/connections",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection_endpoint(
    model_id: uuid.UUID,
    data: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = await create_connection(db, model_id=model_id, user_id=current_user.id, data=data)
    return conn


@router.get(
    "/models/{model_id}/connections",
    response_model=List[ConnectionResponse],
)
async def list_connections_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_connections_for_model(db, model_id=model_id)


@router.get(
    "/connections/{conn_id}",
    response_model=ConnectionResponse,
)
async def get_connection_endpoint(
    conn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = _conn_or_404(await get_connection_by_id(db, conn_id))
    return conn


@router.put(
    "/connections/{conn_id}",
    response_model=ConnectionResponse,
)
async def update_connection_endpoint(
    conn_id: uuid.UUID,
    data: ConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = _conn_or_404(await get_connection_by_id(db, conn_id))
    return await update_connection(db, conn, data)


@router.delete(
    "/connections/{conn_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_connection_endpoint(
    conn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = _conn_or_404(await get_connection_by_id(db, conn_id))
    await delete_connection(db, conn)


# ---------------------------------------------------------------------------
# Schedule routes
# ---------------------------------------------------------------------------

@router.post(
    "/connections/{conn_id}/schedules",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_endpoint(
    conn_id: uuid.UUID,
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _conn_or_404(await get_connection_by_id(db, conn_id))
    try:
        schedule = await create_schedule(db, connection_id=conn_id, data=data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return schedule


@router.get(
    "/connections/{conn_id}/schedules",
    response_model=List[ScheduleResponse],
)
async def list_schedules_endpoint(
    conn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _conn_or_404(await get_connection_by_id(db, conn_id))
    return await list_schedules_for_connection(db, connection_id=conn_id)


@router.get(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
)
async def get_schedule_endpoint(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = _schedule_or_404(await get_schedule_by_id(db, schedule_id))
    return schedule


@router.put(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
)
async def update_schedule_endpoint(
    schedule_id: uuid.UUID,
    data: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = _schedule_or_404(await get_schedule_by_id(db, schedule_id))
    try:
        return await update_schedule(db, schedule, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete(
    "/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule_endpoint(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = _schedule_or_404(await get_schedule_by_id(db, schedule_id))
    await delete_schedule(db, schedule)


@router.put(
    "/schedules/{schedule_id}/enable",
    response_model=ScheduleResponse,
)
async def enable_schedule_endpoint(
    schedule_id: uuid.UUID,
    data: ScheduleEnableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = _schedule_or_404(await get_schedule_by_id(db, schedule_id))
    try:
        return await enable_disable_schedule(db, schedule, data.is_enabled)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/schedules/{schedule_id}/trigger",
    response_model=RunTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_run_endpoint(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _schedule_or_404(await get_schedule_by_id(db, schedule_id))
    run = await trigger_run(db, schedule_id=schedule_id)
    return run


# ---------------------------------------------------------------------------
# Run routes
# ---------------------------------------------------------------------------

@router.get(
    "/schedules/{schedule_id}/runs",
    response_model=List[RunResponse],
)
async def list_runs_endpoint(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _schedule_or_404(await get_schedule_by_id(db, schedule_id))
    return await list_runs_for_schedule(db, schedule_id=schedule_id)


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
)
async def get_run_endpoint(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = _run_or_404(await get_run_by_id(db, run_id))
    return run


@router.post(
    "/runs/{run_id}/execute",
    response_model=RunResponse,
)
async def execute_run_endpoint(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = _run_or_404(await get_run_by_id(db, run_id))
    try:
        return await execute_run(db, run)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/runs/{run_id}/complete",
    response_model=RunResponse,
)
async def complete_run_endpoint(
    run_id: uuid.UUID,
    data: RunCompleteRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = _run_or_404(await get_run_by_id(db, run_id))
    records = data.records_processed if data else None
    return await mark_run_completed(db, run, records_processed=records)


@router.post(
    "/runs/{run_id}/fail",
    response_model=RunResponse,
)
async def fail_run_endpoint(
    run_id: uuid.UUID,
    data: RunFailRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = _run_or_404(await get_run_by_id(db, run_id))
    error_msg = data.error_message if data else None
    return await mark_run_failed(db, run, error_message=error_msg)


@router.post(
    "/runs/{run_id}/retry",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_run_endpoint(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = _run_or_404(await get_run_by_id(db, run_id))
    try:
        new_run = await retry_run(db, run)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return new_run
