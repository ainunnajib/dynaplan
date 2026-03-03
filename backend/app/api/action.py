import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.action import (
    ActionCreate,
    ActionResponse,
    ActionUpdate,
    ProcessCreate,
    ProcessRunResponse,
    ProcessStepCreate,
    ProcessStepResponse,
    ProcessWithStepsResponse,
    ProcessResponse,
)
from app.services.action import (
    add_process_step,
    create_action,
    create_process,
    delete_action,
    get_action_by_id,
    get_process_by_id,
    get_process_runs,
    get_process_step_by_id,
    list_actions_for_model,
    list_processes_for_model,
    remove_process_step,
    run_process,
    update_action,
)

router = APIRouter(tags=["actions"])


def _action_or_404(action) -> object:
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    return action


def _process_or_404(process) -> object:
    if process is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process not found",
        )
    return process


def _step_or_404(step) -> object:
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Process step not found",
        )
    return step


# ---------------------------------------------------------------------------
# Action routes
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/actions",
    response_model=ActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action_endpoint(
    model_id: uuid.UUID,
    data: ActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = await create_action(db, model_id=model_id, data=data)
    return action


@router.get(
    "/models/{model_id}/actions",
    response_model=List[ActionResponse],
)
async def list_actions_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_actions_for_model(db, model_id=model_id)


@router.patch(
    "/actions/{action_id}",
    response_model=ActionResponse,
)
async def update_action_endpoint(
    action_id: uuid.UUID,
    data: ActionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = _action_or_404(await get_action_by_id(db, action_id))
    return await update_action(db, action, data)


@router.delete(
    "/actions/{action_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_action_endpoint(
    action_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = _action_or_404(await get_action_by_id(db, action_id))
    await delete_action(db, action)


# ---------------------------------------------------------------------------
# Process routes
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/processes",
    response_model=ProcessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_process_endpoint(
    model_id: uuid.UUID,
    data: ProcessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    process = await create_process(db, model_id=model_id, data=data)
    return process


@router.get(
    "/models/{model_id}/processes",
    response_model=List[ProcessResponse],
)
async def list_processes_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_processes_for_model(db, model_id=model_id)


@router.get(
    "/processes/{process_id}",
    response_model=ProcessWithStepsResponse,
)
async def get_process_endpoint(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    process = _process_or_404(await get_process_by_id(db, process_id))
    return process


@router.post(
    "/processes/{process_id}/steps",
    response_model=ProcessStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_step_endpoint(
    process_id: uuid.UUID,
    data: ProcessStepCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _process_or_404(await get_process_by_id(db, process_id))
    step = await add_process_step(db, process_id=process_id, data=data)
    return step


@router.delete(
    "/process-steps/{step_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_step_endpoint(
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    step = _step_or_404(await get_process_step_by_id(db, step_id))
    await remove_process_step(db, step)


@router.post(
    "/processes/{process_id}/run",
    response_model=ProcessRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_process_endpoint(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _process_or_404(await get_process_by_id(db, process_id))
    process_run = await run_process(db, process_id=process_id, user_id=current_user.id)
    return process_run


@router.get(
    "/processes/{process_id}/runs",
    response_model=List[ProcessRunResponse],
)
async def list_runs_endpoint(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _process_or_404(await get_process_by_id(db, process_id))
    return await get_process_runs(db, process_id=process_id)
