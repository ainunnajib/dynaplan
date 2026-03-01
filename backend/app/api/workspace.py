import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate
from app.services.workspace import (
    create_workspace,
    delete_workspace,
    get_workspace_by_id,
    list_workspaces_for_owner,
    update_workspace,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


async def _get_owned_workspace(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this workspace",
        )
    return workspace


@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await create_workspace(db, data, owner_id=current_user.id)
    return workspace


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_workspaces_for_owner(db, owner_id=current_user.id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace=Depends(_get_owned_workspace),
):
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def rename_workspace(
    data: WorkspaceUpdate,
    workspace=Depends(_get_owned_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await update_workspace(db, workspace, data)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_workspace(
    workspace=Depends(_get_owned_workspace),
    db: AsyncSession = Depends(get_db),
):
    await delete_workspace(db, workspace)
