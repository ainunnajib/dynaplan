import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


async def create_workspace(
    db: AsyncSession, data: WorkspaceCreate, owner_id: uuid.UUID
) -> Workspace:
    workspace = Workspace(
        name=data.name,
        description=data.description,
        owner_id=owner_id,
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


async def get_workspace_by_id(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Optional[Workspace]:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()


async def list_workspaces_for_owner(
    db: AsyncSession, owner_id: uuid.UUID
) -> List[Workspace]:
    result = await db.execute(
        select(Workspace).where(Workspace.owner_id == owner_id)
    )
    return list(result.scalars().all())


async def update_workspace(
    db: AsyncSession, workspace: Workspace, data: WorkspaceUpdate
) -> Workspace:
    if data.name is not None:
        workspace.name = data.name
    if data.description is not None:
        workspace.description = data.description
    await db.commit()
    await db.refresh(workspace)
    return workspace


async def delete_workspace(db: AsyncSession, workspace: Workspace) -> None:
    await db.delete(workspace)
    await db.commit()
