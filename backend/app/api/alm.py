import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.alm import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
    LockRequest,
    PromotionCreate,
    PromotionResponse,
    RevisionTagCreate,
    RevisionTagResponse,
    TagComparisonResponse,
)
from app.services.alm import (
    compare_revision_tags,
    complete_promotion as svc_complete_promotion,
    create_environment as svc_create_environment,
    create_revision_tag as svc_create_revision_tag,
    fail_promotion as svc_fail_promotion,
    get_environment_by_id,
    get_promotion_by_id,
    get_revision_tag_by_id,
    initiate_promotion as svc_initiate_promotion,
    list_environments_for_model,
    list_promotions_for_env,
    list_revision_tags,
    set_environment_lock as svc_set_lock,
    update_environment as svc_update_environment,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["alm"])


# ---------------------------------------------------------------------------
# Environment CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/models/{model_id}/environments",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_environment(
    model_id: uuid.UUID,
    data: EnvironmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentResponse:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    env = await svc_create_environment(db, model_id, data)
    return EnvironmentResponse.model_validate(env)


@router.get(
    "/models/{model_id}/environments",
    response_model=List[EnvironmentResponse],
)
async def list_environments(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EnvironmentResponse]:
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    envs = await list_environments_for_model(db, model_id)
    return [EnvironmentResponse.model_validate(e) for e in envs]


@router.get(
    "/environments/{env_id}",
    response_model=EnvironmentResponse,
)
async def get_environment(
    env_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentResponse:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return EnvironmentResponse.model_validate(env)


@router.put(
    "/environments/{env_id}",
    response_model=EnvironmentResponse,
)
async def update_environment(
    env_id: uuid.UUID,
    data: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentResponse:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    updated = await svc_update_environment(db, env, data)
    return EnvironmentResponse.model_validate(updated)


@router.put(
    "/environments/{env_id}/lock",
    response_model=EnvironmentResponse,
)
async def lock_environment(
    env_id: uuid.UUID,
    data: LockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentResponse:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    updated = await svc_set_lock(db, env, data)
    return EnvironmentResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Revision Tags
# ---------------------------------------------------------------------------


@router.post(
    "/environments/{env_id}/tags",
    response_model=RevisionTagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_tag(
    env_id: uuid.UUID,
    data: RevisionTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevisionTagResponse:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    tag = await svc_create_revision_tag(db, env_id, current_user.id, data)
    return RevisionTagResponse.model_validate(tag)


@router.get(
    "/environments/{env_id}/tags",
    response_model=List[RevisionTagResponse],
)
async def list_tags(
    env_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[RevisionTagResponse]:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    tags = await list_revision_tags(db, env_id)
    return [RevisionTagResponse.model_validate(t) for t in tags]


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


@router.post(
    "/environments/{env_id}/promote",
    response_model=PromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_promotion(
    env_id: uuid.UUID,
    data: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionResponse:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Source environment not found")
    target = await get_environment_by_id(db, data.target_env_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target environment not found")
    tag = await get_revision_tag_by_id(db, data.revision_tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Revision tag not found")
    record = await svc_initiate_promotion(db, env_id, current_user.id, data)
    return PromotionResponse.model_validate(record)


@router.get(
    "/environments/{env_id}/promotions",
    response_model=List[PromotionResponse],
)
async def list_promotions(
    env_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PromotionResponse]:
    env = await get_environment_by_id(db, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    records = await list_promotions_for_env(db, env_id)
    return [PromotionResponse.model_validate(r) for r in records]


@router.get(
    "/promotions/{promotion_id}",
    response_model=PromotionResponse,
)
async def get_promotion(
    promotion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionResponse:
    record = await get_promotion_by_id(db, promotion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    return PromotionResponse.model_validate(record)


@router.post(
    "/promotions/{promotion_id}/complete",
    response_model=PromotionResponse,
)
async def complete_promotion(
    promotion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionResponse:
    record = await get_promotion_by_id(db, promotion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    try:
        updated = await svc_complete_promotion(db, record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PromotionResponse.model_validate(updated)


@router.post(
    "/promotions/{promotion_id}/fail",
    response_model=PromotionResponse,
)
async def fail_promotion(
    promotion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionResponse:
    record = await get_promotion_by_id(db, promotion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    try:
        updated = await svc_fail_promotion(db, record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PromotionResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Tag comparison
# ---------------------------------------------------------------------------


@router.get(
    "/tags/{tag_id_1}/compare/{tag_id_2}",
    response_model=TagComparisonResponse,
)
async def compare_tags(
    tag_id_1: uuid.UUID,
    tag_id_2: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TagComparisonResponse:
    tag_1 = await get_revision_tag_by_id(db, tag_id_1)
    if tag_1 is None:
        raise HTTPException(status_code=404, detail="First tag not found")
    tag_2 = await get_revision_tag_by_id(db, tag_id_2)
    if tag_2 is None:
        raise HTTPException(status_code=404, detail="Second tag not found")
    return await compare_revision_tags(db, tag_1, tag_2)
