import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.engine_profile import (
    EngineProfileCreate,
    EngineProfileResponse,
    GuidanceCreate,
    GuidanceResponse,
    MetricCreate,
    MetricResponse,
    ModelEvaluationResult,
    ProfileRecommendation,
)
from app.services.planning_model import get_model_by_id
from app.services.engine_profile import (
    create_guidance as svc_create_guidance,
    delete_engine_profile as svc_delete_profile,
    delete_guidance as svc_delete_guidance,
    evaluate_model as svc_evaluate_model,
    get_engine_profile as svc_get_profile,
    get_guidance_by_id,
    list_guidance as svc_list_guidance,
    list_metrics as svc_list_metrics,
    recommend_profile as svc_recommend_profile,
    record_metric as svc_record_metric,
    upsert_engine_profile as svc_upsert_profile,
)

router = APIRouter(tags=["engine-profile"])


# ---------------------------------------------------------------------------
# Engine profile CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/models/{model_id}/engine-profile",
    response_model=EngineProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_engine_profile(
    model_id: uuid.UUID,
    data: EngineProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EngineProfileResponse:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    profile = await svc_upsert_profile(db, model_id, data)
    return EngineProfileResponse.model_validate(profile)


@router.get(
    "/models/{model_id}/engine-profile",
    response_model=EngineProfileResponse,
)
async def get_engine_profile(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EngineProfileResponse:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    profile = await svc_get_profile(db, model_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Engine profile not found")
    return EngineProfileResponse.model_validate(profile)


@router.delete(
    "/models/{model_id}/engine-profile",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_engine_profile(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    profile = await svc_get_profile(db, model_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Engine profile not found")
    await svc_delete_profile(db, profile)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.post(
    "/models/{model_id}/engine-profile/metrics",
    response_model=MetricResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_metric(
    model_id: uuid.UUID,
    data: MetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MetricResponse:
    profile = await svc_get_profile(db, model_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Engine profile not found")
    metric = await svc_record_metric(db, profile.id, data)
    return MetricResponse.model_validate(metric)


@router.get(
    "/models/{model_id}/engine-profile/metrics",
    response_model=List[MetricResponse],
)
async def list_metrics(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MetricResponse]:
    profile = await svc_get_profile(db, model_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Engine profile not found")
    metrics = await svc_list_metrics(db, profile.id)
    return [MetricResponse.model_validate(m) for m in metrics]


# ---------------------------------------------------------------------------
# Evaluate & recommend
# ---------------------------------------------------------------------------


@router.get(
    "/models/{model_id}/engine-profile/evaluate",
    response_model=ModelEvaluationResult,
)
async def evaluate_model(
    model_id: uuid.UUID,
    dimension_count: int = Query(0),
    cell_estimate: int = Query(0),
    line_item_count: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModelEvaluationResult:
    profile = await svc_get_profile(db, model_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Engine profile not found")
    return await svc_evaluate_model(
        db, model_id, profile, dimension_count, cell_estimate, line_item_count
    )


@router.get(
    "/models/{model_id}/engine-profile/recommend",
    response_model=ProfileRecommendation,
)
async def recommend_profile(
    model_id: uuid.UUID,
    dimension_count: int = Query(0),
    cell_estimate: int = Query(0),
    sparsity_ratio: float = Query(0.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileRecommendation:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return await svc_recommend_profile(
        db, model_id, dimension_count, cell_estimate, sparsity_ratio
    )


# ---------------------------------------------------------------------------
# Guidance rules (admin)
# ---------------------------------------------------------------------------


@router.post(
    "/engine-guidance",
    response_model=GuidanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_guidance(
    data: GuidanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GuidanceResponse:
    rule = await svc_create_guidance(db, data)
    return GuidanceResponse.model_validate(rule)


@router.get(
    "/engine-guidance",
    response_model=List[GuidanceResponse],
)
async def list_all_guidance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GuidanceResponse]:
    rules = await svc_list_guidance(db)
    return [GuidanceResponse.model_validate(r) for r in rules]


@router.get(
    "/engine-guidance/{profile_type}",
    response_model=List[GuidanceResponse],
)
async def list_guidance_by_type(
    profile_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[GuidanceResponse]:
    rules = await svc_list_guidance(db, profile_type)
    return [GuidanceResponse.model_validate(r) for r in rules]


@router.delete(
    "/engine-guidance/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_guidance(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    rule = await get_guidance_by_id(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Guidance rule not found")
    await svc_delete_guidance(db, rule)
