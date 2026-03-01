import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineResponse,
    PipelineRunDetail,
    PipelineRunResponse,
    PipelineStepCreate,
    PipelineStepLogResponse,
    PipelineStepResponse,
    PipelineStepUpdate,
    PipelineUpdate,
    PipelineValidationResult,
    PipelineWithSteps,
    StepReorderRequest,
)
from app.services.pipeline import (
    cancel_run as svc_cancel_run,
    create_pipeline as svc_create_pipeline,
    create_step as svc_create_step,
    delete_pipeline as svc_delete_pipeline,
    delete_step as svc_delete_step,
    get_pipeline_by_id,
    get_run_by_id,
    get_step_by_id,
    list_pipelines_for_model,
    list_runs_for_pipeline,
    reorder_steps as svc_reorder_steps,
    trigger_pipeline_run as svc_trigger_pipeline_run,
    update_pipeline as svc_update_pipeline,
    update_step as svc_update_step,
    validate_pipeline as svc_validate_pipeline,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["pipeline"])


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/models/{model_id}/pipelines",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline(
    model_id: uuid.UUID,
    data: PipelineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineResponse:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    pipeline = await svc_create_pipeline(db, model_id, current_user.id, data)
    return PipelineResponse.model_validate(pipeline)


@router.get(
    "/models/{model_id}/pipelines",
    response_model=List[PipelineResponse],
)
async def list_pipelines(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PipelineResponse]:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    pipelines = await list_pipelines_for_model(db, model_id)
    return [PipelineResponse.model_validate(p) for p in pipelines]


@router.get(
    "/pipelines/{pipeline_id}",
    response_model=PipelineWithSteps,
)
async def get_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineWithSteps:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    detail = PipelineWithSteps.model_validate(pipeline)
    detail.steps = [PipelineStepResponse.model_validate(s) for s in pipeline.steps]
    return detail


@router.put(
    "/pipelines/{pipeline_id}",
    response_model=PipelineResponse,
)
async def update_pipeline(
    pipeline_id: uuid.UUID,
    data: PipelineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineResponse:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    updated = await svc_update_pipeline(db, pipeline, data)
    return PipelineResponse.model_validate(updated)


@router.delete(
    "/pipelines/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    await svc_delete_pipeline(db, pipeline)


# ---------------------------------------------------------------------------
# Pipeline Step CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/pipelines/{pipeline_id}/steps",
    response_model=PipelineStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_step(
    pipeline_id: uuid.UUID,
    data: PipelineStepCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineStepResponse:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    try:
        step = await svc_create_step(db, pipeline_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PipelineStepResponse.model_validate(step)


@router.put(
    "/steps/{step_id}",
    response_model=PipelineStepResponse,
)
async def update_step(
    step_id: uuid.UUID,
    data: PipelineStepUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineStepResponse:
    step = await get_step_by_id(db, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    try:
        updated = await svc_update_step(db, step, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PipelineStepResponse.model_validate(updated)


@router.delete(
    "/steps/{step_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_step(
    step_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    step = await get_step_by_id(db, step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    await svc_delete_step(db, step)


@router.post(
    "/pipelines/{pipeline_id}/steps/reorder",
    response_model=List[PipelineStepResponse],
)
async def reorder_steps(
    pipeline_id: uuid.UUID,
    data: StepReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PipelineStepResponse]:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    try:
        steps = await svc_reorder_steps(db, pipeline_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [PipelineStepResponse.model_validate(s) for s in steps]


# ---------------------------------------------------------------------------
# Pipeline Run
# ---------------------------------------------------------------------------


@router.post(
    "/pipelines/{pipeline_id}/trigger",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_run(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineRunResponse:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    try:
        run = await svc_trigger_pipeline_run(db, pipeline, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PipelineRunResponse.model_validate(run)


@router.get(
    "/pipelines/{pipeline_id}/runs",
    response_model=List[PipelineRunResponse],
)
async def list_runs(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PipelineRunResponse]:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    runs = await list_runs_for_pipeline(db, pipeline_id)
    return [PipelineRunResponse.model_validate(r) for r in runs]


@router.get(
    "/pipeline-runs/{run_id}",
    response_model=PipelineRunDetail,
)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineRunDetail:
    run = await get_run_by_id(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    detail = PipelineRunDetail.model_validate(run)
    detail.step_logs = [PipelineStepLogResponse.model_validate(sl) for sl in run.step_logs]
    return detail


@router.post(
    "/pipeline-runs/{run_id}/cancel",
    response_model=PipelineRunResponse,
)
async def cancel_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineRunResponse:
    run = await get_run_by_id(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        updated = await svc_cancel_run(db, run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PipelineRunResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@router.get(
    "/pipelines/{pipeline_id}/validate",
    response_model=PipelineValidationResult,
)
async def validate_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineValidationResult:
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return await svc_validate_pipeline(db, pipeline)
