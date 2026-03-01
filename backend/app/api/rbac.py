import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.rbac import WorkspaceRole
from app.schemas.rbac import (
    DimensionAccessCreate,
    DimensionAccessResponse,
    ModelAccessCreate,
    ModelAccessResponse,
    MyPermissionsResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
)
from app.services.auth import get_user_by_email, get_user_by_id
from app.services.rbac import (
    add_workspace_member,
    check_workspace_permission,
    get_model_access,
    get_workspace_role,
    list_dimension_access_for_user,
    list_model_access,
    list_workspace_members,
    remove_model_access,
    remove_workspace_member,
    set_dimension_access,
    set_model_access,
)
from app.services.workspace import get_workspace_by_id
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["rbac"])


# ---------------------------------------------------------------------------
# Workspace Members
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    workspace_id: uuid.UUID,
    data: WorkspaceMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    # Only the workspace owner or an admin can add members
    if workspace.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    target_user = await get_user_by_email(db, data.user_email)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    member = await add_workspace_member(db, workspace_id, target_user.id, data.role)
    return WorkspaceMemberResponse(
        user_id=member.user_id,
        email=member.user.email,
        full_name=member.user.full_name,
        role=member.role,
    )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=List[WorkspaceMemberResponse],
)
async def list_members(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    # Only members and the owner can list members
    if workspace.owner_id != current_user.id:
        role = await get_workspace_role(db, workspace_id, current_user.id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    members = await list_workspace_members(db, workspace_id)
    return [
        WorkspaceMemberResponse(
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
        )
        for m in members
    ]


@router.patch(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: WorkspaceMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if workspace.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Cannot change owner's role
    if user_id == workspace.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change the workspace owner's role",
        )

    target_user = await get_user_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing_role = await get_workspace_role(db, workspace_id, user_id)
    if existing_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    member = await add_workspace_member(db, workspace_id, user_id, data.role)
    return WorkspaceMemberResponse(
        user_id=member.user_id,
        email=member.user.email,
        full_name=member.user.full_name,
        role=member.role,
    )


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if workspace.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Cannot remove workspace owner
    if user_id == workspace.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the workspace owner",
        )

    removed = await remove_workspace_member(db, workspace_id, user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")


# ---------------------------------------------------------------------------
# Model Access
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/access",
    response_model=ModelAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_access(
    model_id: uuid.UUID,
    data: ModelAccessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    # Only the model owner or workspace admin/owner can set access
    if model.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, model.workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    target_user = await get_user_by_email(db, data.user_email)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    access = await set_model_access(db, model_id, target_user.id, data.permission)
    return ModelAccessResponse(
        user_id=access.user_id,
        email=access.user.email,
        permission=access.permission,
    )


@router.get(
    "/models/{model_id}/access",
    response_model=List[ModelAccessResponse],
)
async def list_access(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if model.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, model.workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    access_list = await list_model_access(db, model_id)
    return [
        ModelAccessResponse(
            user_id=a.user_id,
            email=a.user.email,
            permission=a.permission,
        )
        for a in access_list
    ]


@router.delete(
    "/models/{model_id}/access/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_access(
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if model.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, model.workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    removed = await remove_model_access(db, model_id, user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access rule not found")


# ---------------------------------------------------------------------------
# Dimension Member Access
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/dimension-access",
    response_model=DimensionAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_dim_access(
    model_id: uuid.UUID,
    data: DimensionAccessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if model.owner_id != current_user.id:
        has_permission = await check_workspace_permission(
            db, model.workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    access = await set_dimension_access(
        db, model_id, current_user.id, data.dimension_id, data.allowed_member_ids
    )
    return DimensionAccessResponse(
        dimension_id=access.dimension_id,
        allowed_member_ids=access.allowed_member_ids or [],
    )


@router.get(
    "/models/{model_id}/dimension-access/{user_id}",
    response_model=List[DimensionAccessResponse],
)
async def get_dim_access(
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if model.owner_id != current_user.id and current_user.id != user_id:
        has_permission = await check_workspace_permission(
            db, model.workspace_id, current_user.id, WorkspaceRole.admin
        )
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    access_list = await list_dimension_access_for_user(db, model_id, user_id)
    return [
        DimensionAccessResponse(
            dimension_id=a.dimension_id,
            allowed_member_ids=a.allowed_member_ids or [],
        )
        for a in access_list
    ]


# ---------------------------------------------------------------------------
# Current user permissions
# ---------------------------------------------------------------------------

@router.get("/me/permissions", response_model=MyPermissionsResponse)
async def get_my_permissions(
    workspace_id: Optional[uuid.UUID] = Query(None),
    model_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace_role = None
    model_permission = None

    if workspace_id is not None:
        workspace = await get_workspace_by_id(db, workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )
        if workspace.owner_id == current_user.id:
            workspace_role = WorkspaceRole.owner
        else:
            workspace_role = await get_workspace_role(db, workspace_id, current_user.id)

    if model_id is not None:
        model = await get_model_by_id(db, model_id)
        if model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
        model_permission = await get_model_access(db, model_id, current_user.id)

    return MyPermissionsResponse(
        workspace_role=workspace_role,
        model_permission=model_permission,
    )
