import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.workflow import (
    ApprovalCreate,
    StageCreate,
    StageResponse,
    StageUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    WorkflowCreate,
    WorkflowDetail,
    WorkflowProgress,
    WorkflowResponse,
    WorkflowUpdate,
    StageWithTasks,
)
from app.services.planning_model import get_model_by_id
from app.services.workflow import (
    activate_workflow as svc_activate_workflow,
    approve_task as svc_approve_task,
    complete_workflow as svc_complete_workflow,
    create_stage as svc_create_stage,
    create_task as svc_create_task,
    create_workflow as svc_create_workflow,
    delete_stage as svc_delete_stage,
    delete_workflow as svc_delete_workflow,
    get_stage_by_id,
    get_task_by_id,
    get_workflow_by_id,
    get_workflow_progress as svc_get_workflow_progress,
    list_workflows_for_model,
    reject_task as svc_reject_task,
    submit_task as svc_submit_task,
    update_stage as svc_update_stage,
    update_task as svc_update_task,
    update_workflow as svc_update_workflow,
)

router = APIRouter(tags=["workflow"])


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/models/{model_id}/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    model_id: uuid.UUID,
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResponse:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    workflow = await svc_create_workflow(db, model_id, current_user.id, data)
    return WorkflowResponse.model_validate(workflow)


@router.get(
    "/models/{model_id}/workflows",
    response_model=List[WorkflowResponse],
)
async def list_workflows(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WorkflowResponse]:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    workflows = await list_workflows_for_model(db, model_id)
    return [WorkflowResponse.model_validate(w) for w in workflows]


@router.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowDetail,
)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowDetail:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    stages_with_tasks = []
    for stage in workflow.stages:
        st = StageWithTasks.model_validate(stage)
        st.tasks = [TaskResponse.model_validate(t) for t in stage.tasks]
        stages_with_tasks.append(st)
    detail = WorkflowDetail.model_validate(workflow)
    detail.stages = stages_with_tasks
    return detail


@router.put(
    "/workflows/{workflow_id}",
    response_model=WorkflowResponse,
)
async def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResponse:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    updated = await svc_update_workflow(db, workflow, data)
    return WorkflowResponse.model_validate(updated)


@router.delete(
    "/workflows/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await svc_delete_workflow(db, workflow)


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/workflows/{workflow_id}/stages",
    response_model=StageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stage(
    workflow_id: uuid.UUID,
    data: StageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StageResponse:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    stage = await svc_create_stage(db, workflow_id, data)
    return StageResponse.model_validate(stage)


@router.put(
    "/stages/{stage_id}",
    response_model=StageResponse,
)
async def update_stage(
    stage_id: uuid.UUID,
    data: StageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StageResponse:
    stage = await get_stage_by_id(db, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    updated = await svc_update_stage(db, stage, data)
    return StageResponse.model_validate(updated)


@router.delete(
    "/stages/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_stage(
    stage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stage = await get_stage_by_id(db, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    await svc_delete_stage(db, stage)


# ---------------------------------------------------------------------------
# Task CRUD & lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/stages/{stage_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    stage_id: uuid.UUID,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    stage = await get_stage_by_id(db, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    task = await svc_create_task(db, stage_id, data)
    return TaskResponse.model_validate(task)


@router.put(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    task = await get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    updated = await svc_update_task(db, task, data)
    return TaskResponse.model_validate(updated)


@router.post(
    "/tasks/{task_id}/submit",
    response_model=TaskResponse,
)
async def submit_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    task = await get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        updated = await svc_submit_task(db, task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TaskResponse.model_validate(updated)


@router.post(
    "/tasks/{task_id}/approve",
    response_model=TaskResponse,
)
async def approve_task(
    task_id: uuid.UUID,
    data: ApprovalCreate = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    task = await get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if data is None:
        data = ApprovalCreate()
    try:
        updated = await svc_approve_task(db, task, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TaskResponse.model_validate(updated)


@router.post(
    "/tasks/{task_id}/reject",
    response_model=TaskResponse,
)
async def reject_task(
    task_id: uuid.UUID,
    data: ApprovalCreate = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    task = await get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if data is None:
        data = ApprovalCreate()
    try:
        updated = await svc_reject_task(db, task, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TaskResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Workflow lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/workflows/{workflow_id}/activate",
    response_model=WorkflowResponse,
)
async def activate_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResponse:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        updated = await svc_activate_workflow(db, workflow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WorkflowResponse.model_validate(updated)


@router.post(
    "/workflows/{workflow_id}/complete",
    response_model=WorkflowResponse,
)
async def complete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowResponse:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        updated = await svc_complete_workflow(db, workflow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WorkflowResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


@router.get(
    "/workflows/{workflow_id}/progress",
    response_model=WorkflowProgress,
)
async def get_workflow_progress(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowProgress:
    workflow = await get_workflow_by_id(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return await svc_get_workflow_progress(db, workflow)
