import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.planning_model import (
    PlanningModelClone,
    PlanningModelCreate,
    PlanningModelResponse,
    PlanningModelUpdate,
)
from app.services.planning_model import (
    archive_model,
    clone_model,
    create_model,
    delete_model,
    get_model_by_id,
    list_models_for_workspace,
    unarchive_model,
    update_model,
)

router = APIRouter(prefix="/models", tags=["models"])


def _get_model_or_404(model):
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    return model


@router.post("", response_model=PlanningModelResponse, status_code=status.HTTP_201_CREATED)
async def create_planning_model(
    data: PlanningModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await create_model(db, data, owner_id=current_user.id)
    return model


@router.get("/workspace/{workspace_id}", response_model=list[PlanningModelResponse])
async def list_workspace_models(
    workspace_id: uuid.UUID,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    models = await list_models_for_workspace(db, workspace_id, include_archived=include_archived)
    return models


@router.get("/{model_id}", response_model=PlanningModelResponse)
async def get_planning_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _get_model_or_404(await get_model_by_id(db, model_id))
    return model


@router.patch("/{model_id}", response_model=PlanningModelResponse)
async def update_planning_model(
    model_id: uuid.UUID,
    data: PlanningModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _get_model_or_404(await get_model_by_id(db, model_id))
    model = await update_model(db, model, data)
    return model


@router.post("/{model_id}/archive", response_model=PlanningModelResponse)
async def archive_planning_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _get_model_or_404(await get_model_by_id(db, model_id))
    model = await archive_model(db, model)
    return model


@router.post("/{model_id}/unarchive", response_model=PlanningModelResponse)
async def unarchive_planning_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _get_model_or_404(await get_model_by_id(db, model_id))
    model = await unarchive_model(db, model)
    return model


@router.post("/{model_id}/clone", response_model=PlanningModelResponse, status_code=status.HTTP_201_CREATED)
async def clone_planning_model(
    model_id: uuid.UUID,
    data: PlanningModelClone,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = _get_model_or_404(await get_model_by_id(db, model_id))
    cloned = await clone_model(
        db,
        source,
        new_name=data.name,
        owner_id=current_user.id,
        workspace_id=data.workspace_id,
    )
    return cloned


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planning_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _get_model_or_404(await get_model_by_id(db, model_id))
    await delete_model(db, model)
