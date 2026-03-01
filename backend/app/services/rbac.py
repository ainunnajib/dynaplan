import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac import (
    DimensionMemberAccess,
    ModelAccess,
    ModelPermission,
    WorkspaceMember,
    WorkspaceRole,
)

# Role hierarchy for permission checks: higher index = higher privilege
_ROLE_ORDER = [
    WorkspaceRole.viewer,
    WorkspaceRole.editor,
    WorkspaceRole.admin,
    WorkspaceRole.owner,
]

# Permission hierarchy: higher index = more access
_PERMISSION_ORDER = [
    ModelPermission.no_access,
    ModelPermission.view_only,
    ModelPermission.edit_data,
    ModelPermission.full_access,
]


async def add_workspace_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceRole,
) -> WorkspaceMember:
    """Add or update a workspace member's role."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.role = role
        await db.commit()
        await db.refresh(existing)
        return existing

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_workspace_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Remove a member from a workspace. Returns True if removed, False if not found."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return False
    await db.delete(member)
    await db.commit()
    return True


async def list_workspace_members(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> List[WorkspaceMember]:
    """List all members of a workspace."""
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    return list(result.scalars().all())


async def get_workspace_role(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optional[WorkspaceRole]:
    """Get the role of a user in a workspace, or None if not a member."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    return member.role if member is not None else None


async def check_workspace_permission(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    min_role: WorkspaceRole,
) -> bool:
    """Check if a user has at least min_role in a workspace."""
    role = await get_workspace_role(db, workspace_id, user_id)
    if role is None:
        return False
    try:
        user_level = _ROLE_ORDER.index(role)
        min_level = _ROLE_ORDER.index(min_role)
    except ValueError:
        return False
    return user_level >= min_level


async def set_model_access(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: ModelPermission,
) -> ModelAccess:
    """Set (create or update) a user's permission on a model."""
    result = await db.execute(
        select(ModelAccess).where(
            ModelAccess.model_id == model_id,
            ModelAccess.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.permission = permission
        await db.commit()
        await db.refresh(existing)
        return existing

    access = ModelAccess(
        model_id=model_id,
        user_id=user_id,
        permission=permission,
    )
    db.add(access)
    await db.commit()
    await db.refresh(access)
    return access


async def get_model_access(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optional[ModelPermission]:
    """Get a user's permission level on a model, or None if not set."""
    result = await db.execute(
        select(ModelAccess).where(
            ModelAccess.model_id == model_id,
            ModelAccess.user_id == user_id,
        )
    )
    access = result.scalar_one_or_none()
    return access.permission if access is not None else None


async def list_model_access(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[ModelAccess]:
    """List all access rules for a model."""
    result = await db.execute(
        select(ModelAccess).where(ModelAccess.model_id == model_id)
    )
    return list(result.scalars().all())


async def remove_model_access(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Remove a user's access to a model. Returns True if removed, False if not found."""
    result = await db.execute(
        select(ModelAccess).where(
            ModelAccess.model_id == model_id,
            ModelAccess.user_id == user_id,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        return False
    await db.delete(access)
    await db.commit()
    return True


async def check_model_permission(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    required_permission: ModelPermission,
) -> bool:
    """Returns True if the user has at least required_permission on the model."""
    permission = await get_model_access(db, model_id, user_id)
    if permission is None:
        return False
    try:
        user_level = _PERMISSION_ORDER.index(permission)
        required_level = _PERMISSION_ORDER.index(required_permission)
    except ValueError:
        return False
    return user_level >= required_level


async def set_dimension_access(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    dimension_id: uuid.UUID,
    allowed_member_ids: List[str],
) -> DimensionMemberAccess:
    """Set selective dimension member access for a user."""
    result = await db.execute(
        select(DimensionMemberAccess).where(
            DimensionMemberAccess.model_id == model_id,
            DimensionMemberAccess.user_id == user_id,
            DimensionMemberAccess.dimension_id == dimension_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.allowed_member_ids = allowed_member_ids
        await db.commit()
        await db.refresh(existing)
        return existing

    access = DimensionMemberAccess(
        model_id=model_id,
        user_id=user_id,
        dimension_id=dimension_id,
        allowed_member_ids=allowed_member_ids,
    )
    db.add(access)
    await db.commit()
    await db.refresh(access)
    return access


async def get_dimension_access(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    dimension_id: uuid.UUID,
) -> Optional[DimensionMemberAccess]:
    """Get dimension member access for a user, or None if not set."""
    result = await db.execute(
        select(DimensionMemberAccess).where(
            DimensionMemberAccess.model_id == model_id,
            DimensionMemberAccess.user_id == user_id,
            DimensionMemberAccess.dimension_id == dimension_id,
        )
    )
    return result.scalar_one_or_none()


async def list_dimension_access_for_user(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
) -> List[DimensionMemberAccess]:
    """List all dimension access rules for a user on a model."""
    result = await db.execute(
        select(DimensionMemberAccess).where(
            DimensionMemberAccess.model_id == model_id,
            DimensionMemberAccess.user_id == user_id,
        )
    )
    return list(result.scalars().all())
