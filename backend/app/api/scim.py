import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.scim import (
    SCIMConfigCreate,
    SCIMConfigResponse,
    SCIMConfigUpdate,
    SCIMGroupCreate,
    SCIMListResponse,
    SCIMPatchRequest,
    SCIMProvisioningLogResponse,
    SCIMUserCreate,
)
from app.services.scim import (
    create_scim_config,
    create_scim_group,
    create_scim_user,
    deactivate_scim_user,
    delete_scim_group,
    get_provisioning_logs,
    get_scim_config,
    get_scim_group,
    get_scim_user,
    group_to_scim_resource,
    list_scim_groups,
    list_scim_users,
    update_scim_config,
    update_scim_group,
    update_scim_user,
    user_to_scim_resource,
    validate_scim_token,
)
from app.services.workspace import get_workspace_by_id

router = APIRouter(tags=["scim"])


# ---------------------------------------------------------------------------
# SCIM bearer token auth dependency
# ---------------------------------------------------------------------------

async def get_scim_auth(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Extract and validate SCIM bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid SCIM bearer token",
        )
    token = authorization[7:]
    config = await validate_scim_token(db, token)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SCIM bearer token",
        )
    return config


# ---------------------------------------------------------------------------
# Workspace owner dependency
# ---------------------------------------------------------------------------

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
            detail="Not authorized to manage SCIM for this workspace",
        )
    return workspace


# ---------------------------------------------------------------------------
# Config endpoints (JWT-protected)
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/scim/config",
    response_model=SCIMConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_config(
    workspace_id: uuid.UUID,
    data: SCIMConfigCreate,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    existing = await get_scim_config(db, workspace_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SCIM config already exists for this workspace",
        )
    config = await create_scim_config(
        db,
        workspace_id=workspace_id,
        bearer_token=data.bearer_token,
        base_url=data.base_url,
        is_enabled=data.is_enabled,
    )
    return config


@router.get(
    "/workspaces/{workspace_id}/scim/config",
    response_model=SCIMConfigResponse,
)
async def get_config(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    config = await get_scim_config(db, workspace_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SCIM config for this workspace",
        )
    return config


@router.put(
    "/workspaces/{workspace_id}/scim/config",
    response_model=SCIMConfigResponse,
)
async def update_config(
    workspace_id: uuid.UUID,
    data: SCIMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    config = await get_scim_config(db, workspace_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SCIM config for this workspace",
        )
    updated = await update_scim_config(
        db,
        config,
        bearer_token=data.bearer_token,
        base_url=data.base_url,
        is_enabled=data.is_enabled,
    )
    return updated


# ---------------------------------------------------------------------------
# Provisioning Logs (JWT-protected)
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/scim/logs",
    response_model=list,
)
async def get_logs(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    logs = await get_provisioning_logs(db, workspace_id)
    return [
        SCIMProvisioningLogResponse.model_validate(log).model_dump()
        for log in logs
    ]


# ---------------------------------------------------------------------------
# SCIM v2 User endpoints (SCIM bearer token auth)
# ---------------------------------------------------------------------------

@router.get("/scim/v2/Users")
async def scim_list_users(
    startIndex: int = 1,
    count: int = 100,
    filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    users, total = await list_scim_users(db, start_index=startIndex, count=count, filter_str=filter)
    resources = [user_to_scim_resource(u, config.base_url) for u in users]
    return SCIMListResponse(
        totalResults=total,
        itemsPerPage=len(users),
        startIndex=startIndex,
        Resources=resources,
    ).model_dump()


@router.get("/scim/v2/Users/{user_id}")
async def scim_get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    user = await get_scim_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user_to_scim_resource(user, config.base_url)


@router.post("/scim/v2/Users", status_code=status.HTTP_201_CREATED)
async def scim_create_user(
    data: SCIMUserCreate,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    # Check if user already exists
    from app.services.auth import get_user_by_email
    existing = await get_user_by_email(db, data.userName)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    display_name = data.displayName
    if not display_name and data.name:
        display_name = data.name.formatted
    if not display_name:
        display_name = data.userName

    user = await create_scim_user(
        db,
        workspace_id=config.workspace_id,
        user_name=data.userName,
        display_name=display_name,
        external_id=data.externalId,
        active=data.active,
        password=data.password,
    )
    return user_to_scim_resource(user, config.base_url)


@router.put("/scim/v2/Users/{user_id}")
async def scim_update_user(
    user_id: uuid.UUID,
    data: SCIMUserCreate,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    user = await get_scim_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    display_name = data.displayName
    if not display_name and data.name:
        display_name = data.name.formatted

    updated = await update_scim_user(
        db,
        workspace_id=config.workspace_id,
        user=user,
        user_name=data.userName,
        display_name=display_name,
        active=data.active,
        external_id=data.externalId,
    )
    return user_to_scim_resource(updated, config.base_url)


@router.patch("/scim/v2/Users/{user_id}")
async def scim_patch_user(
    user_id: uuid.UUID,
    data: SCIMPatchRequest,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    user = await get_scim_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    for op in data.Operations:
        if op.op.lower() == "replace":
            if op.path == "active" or (op.path is None and isinstance(op.value, dict) and "active" in op.value):
                active_val = op.value if isinstance(op.value, bool) else op.value.get("active", True)
                if not active_val:
                    user = await deactivate_scim_user(db, config.workspace_id, user)
                else:
                    user = await update_scim_user(
                        db, config.workspace_id, user, active=True
                    )
            elif op.path == "displayName" or op.path == "name.formatted":
                user = await update_scim_user(
                    db, config.workspace_id, user, display_name=op.value
                )
            elif op.path is None and isinstance(op.value, dict):
                # Bulk replace
                kwargs = {}
                if "active" in op.value:
                    kwargs["active"] = op.value["active"]
                if "displayName" in op.value:
                    kwargs["display_name"] = op.value["displayName"]
                if "userName" in op.value:
                    kwargs["user_name"] = op.value["userName"]
                if kwargs:
                    user = await update_scim_user(
                        db, config.workspace_id, user, **kwargs
                    )

    return user_to_scim_resource(user, config.base_url)


# ---------------------------------------------------------------------------
# SCIM v2 Group endpoints (SCIM bearer token auth)
# ---------------------------------------------------------------------------

@router.get("/scim/v2/Groups")
async def scim_list_groups(
    startIndex: int = 1,
    count: int = 100,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    groups, total = await list_scim_groups(
        db, config.workspace_id, start_index=startIndex, count=count
    )
    resources = [group_to_scim_resource(g, config.base_url) for g in groups]
    return SCIMListResponse(
        totalResults=total,
        itemsPerPage=len(groups),
        startIndex=startIndex,
        Resources=resources,
    ).model_dump()


@router.get("/scim/v2/Groups/{group_id}")
async def scim_get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    group = await get_scim_group(db, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    return group_to_scim_resource(group, config.base_url)


@router.post("/scim/v2/Groups", status_code=status.HTTP_201_CREATED)
async def scim_create_group(
    data: SCIMGroupCreate,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    member_ids = None
    if data.members:
        member_ids = [m.value for m in data.members]

    group = await create_scim_group(
        db,
        workspace_id=config.workspace_id,
        display_name=data.displayName,
        external_id=data.externalId,
        member_ids=member_ids,
    )
    return group_to_scim_resource(group, config.base_url)


@router.put("/scim/v2/Groups/{group_id}")
async def scim_update_group(
    group_id: uuid.UUID,
    data: SCIMGroupCreate,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    group = await get_scim_group(db, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    member_ids = None
    if data.members is not None:
        member_ids = [m.value for m in data.members]

    updated = await update_scim_group(
        db,
        workspace_id=config.workspace_id,
        group=group,
        display_name=data.displayName,
        external_id=data.externalId,
        member_ids=member_ids,
    )
    return group_to_scim_resource(updated, config.base_url)


@router.delete("/scim/v2/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def scim_delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    config=Depends(get_scim_auth),
):
    group = await get_scim_group(db, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    await delete_scim_group(db, config.workspace_id, group)
