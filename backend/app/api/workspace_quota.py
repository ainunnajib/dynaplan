import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.workspace_quota import (
    WorkspaceQuotaResponse,
    WorkspaceQuotaUpdate,
    WorkspaceQuotaUsageResponse,
)
from app.services.workspace import get_workspace_by_id
from app.services.workspace_quota import (
    WorkspaceQuotaValidationError,
    ensure_workspace_quota,
    get_workspace_quota_usage,
    update_workspace_quota,
)

router = APIRouter(tags=["workspace-quotas"])


async def _require_workspace_owner(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.get(
    "/workspaces/{workspace_id}/quota",
    response_model=WorkspaceQuotaResponse,
)
async def get_workspace_quota_endpoint(
    workspace_id: uuid.UUID,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    return await ensure_workspace_quota(db, workspace_id)


@router.put(
    "/workspaces/{workspace_id}/quota",
    response_model=WorkspaceQuotaResponse,
)
async def update_workspace_quota_endpoint(
    workspace_id: uuid.UUID,
    data: WorkspaceQuotaUpdate,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    quota = await ensure_workspace_quota(db, workspace_id)
    try:
        return await update_workspace_quota(
            db,
            quota,
            max_models=data.max_models,
            max_cells_per_model=data.max_cells_per_model,
            max_dimensions_per_model=data.max_dimensions_per_model,
            storage_limit_mb=data.storage_limit_mb,
        )
    except WorkspaceQuotaValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/workspaces/{workspace_id}/quota/usage",
    response_model=WorkspaceQuotaUsageResponse,
)
async def get_workspace_quota_usage_endpoint(
    workspace_id: uuid.UUID,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    usage = await get_workspace_quota_usage(db, workspace_id)
    return WorkspaceQuotaUsageResponse(**usage)
