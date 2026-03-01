import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planning_model import PlanningModel
from app.schemas.planning_model import PlanningModelCreate, PlanningModelUpdate
from app.services.workspace_quota import enforce_model_creation_quota


async def get_model_by_id(
    db: AsyncSession, model_id: uuid.UUID
) -> Optional[PlanningModel]:
    result = await db.execute(
        select(PlanningModel).where(PlanningModel.id == model_id)
    )
    return result.scalar_one_or_none()


async def list_models_for_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    include_archived: bool = False,
) -> list[PlanningModel]:
    stmt = select(PlanningModel).where(PlanningModel.workspace_id == workspace_id)
    if not include_archived:
        stmt = stmt.where(PlanningModel.is_archived == False)  # noqa: E712
    stmt = stmt.order_by(PlanningModel.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_model(
    db: AsyncSession,
    data: PlanningModelCreate,
    owner_id: uuid.UUID,
) -> PlanningModel:
    await enforce_model_creation_quota(db, data.workspace_id)

    model = PlanningModel(
        name=data.name,
        description=data.description,
        workspace_id=data.workspace_id,
        owner_id=owner_id,
        settings=data.settings or {},
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def update_model(
    db: AsyncSession,
    model: PlanningModel,
    data: PlanningModelUpdate,
) -> PlanningModel:
    if data.name is not None:
        model.name = data.name
    if data.description is not None:
        model.description = data.description
    if data.settings is not None:
        model.settings = data.settings
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def archive_model(
    db: AsyncSession, model: PlanningModel
) -> PlanningModel:
    model.is_archived = True
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def unarchive_model(
    db: AsyncSession, model: PlanningModel
) -> PlanningModel:
    model.is_archived = False
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def clone_model(
    db: AsyncSession,
    source: PlanningModel,
    new_name: str,
    owner_id: uuid.UUID,
    workspace_id: Optional[uuid.UUID] = None,
) -> PlanningModel:
    """Clone a model into the same or a different workspace."""
    target_workspace_id = (
        workspace_id if workspace_id is not None else source.workspace_id
    )
    await enforce_model_creation_quota(db, target_workspace_id)

    cloned = PlanningModel(
        name=new_name,
        description=source.description,
        workspace_id=target_workspace_id,
        owner_id=owner_id,
        settings=dict(source.settings) if source.settings else {},
    )
    db.add(cloned)
    await db.commit()
    await db.refresh(cloned)
    return cloned


async def delete_model(db: AsyncSession, model: PlanningModel) -> None:
    await db.delete(model)
    await db.commit()
