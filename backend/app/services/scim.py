import secrets
import uuid
from typing import Any, Dict, List, Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.scim import (
    SCIMConfig,
    SCIMGroup,
    SCIMGroupMember,
    SCIMLogStatus,
    SCIMOperation,
    SCIMProvisioningLog,
)
from app.models.user import User
from app.services.auth import hash_password

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def hash_bearer_token(token: str) -> str:
    return pwd_context.hash(token)


def verify_bearer_token(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# SCIM Config CRUD
# ---------------------------------------------------------------------------

async def create_scim_config(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    bearer_token: str,
    base_url: str = "http://localhost:8000",
    is_enabled: bool = True,
) -> SCIMConfig:
    config = SCIMConfig(
        workspace_id=workspace_id,
        bearer_token_hash=hash_bearer_token(bearer_token),
        base_url=base_url,
        is_enabled=is_enabled,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def get_scim_config(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Optional[SCIMConfig]:
    result = await db.execute(
        select(SCIMConfig).where(SCIMConfig.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def update_scim_config(
    db: AsyncSession,
    config: SCIMConfig,
    bearer_token: Optional[str] = None,
    base_url: Optional[str] = None,
    is_enabled: Optional[bool] = None,
) -> SCIMConfig:
    if bearer_token is not None:
        config.bearer_token_hash = hash_bearer_token(bearer_token)
    if base_url is not None:
        config.base_url = base_url
    if is_enabled is not None:
        config.is_enabled = is_enabled
    await db.commit()
    await db.refresh(config)
    return config


async def delete_scim_config(db: AsyncSession, config: SCIMConfig) -> None:
    await db.delete(config)
    await db.commit()


# ---------------------------------------------------------------------------
# Token validation (for SCIM v2 endpoints)
# ---------------------------------------------------------------------------

async def validate_scim_token(
    db: AsyncSession, token: str
) -> Optional[SCIMConfig]:
    """Validate a SCIM bearer token. Returns the config if valid, else None."""
    # We need to check all configs — token is hashed so we can't query by it.
    result = await db.execute(select(SCIMConfig).where(SCIMConfig.is_enabled.is_(True)))
    configs = result.scalars().all()
    for config in configs:
        if verify_bearer_token(token, config.bearer_token_hash):
            return config
    return None


# ---------------------------------------------------------------------------
# Provisioning Log
# ---------------------------------------------------------------------------

async def log_provisioning(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    operation: SCIMOperation,
    resource_type: str,
    resource_id: str,
    status: SCIMLogStatus,
    external_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> SCIMProvisioningLog:
    log = SCIMProvisioningLog(
        workspace_id=workspace_id,
        operation=operation,
        resource_type=resource_type,
        resource_id=str(resource_id),
        external_id=external_id,
        status=status,
        error_message=error_message,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_provisioning_logs(
    db: AsyncSession, workspace_id: uuid.UUID, limit: int = 100
) -> List[SCIMProvisioningLog]:
    result = await db.execute(
        select(SCIMProvisioningLog)
        .where(SCIMProvisioningLog.workspace_id == workspace_id)
        .order_by(SCIMProvisioningLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# SCIM User operations
# ---------------------------------------------------------------------------

async def list_scim_users(
    db: AsyncSession,
    start_index: int = 1,
    count: int = 100,
    filter_str: Optional[str] = None,
) -> Tuple[List[User], int]:
    """List users in SCIM format. Returns (users, total_count)."""
    query = select(User)

    # Simple userName filter support: filter=userName eq "value"
    if filter_str:
        import re
        match = re.match(r'userName\s+eq\s+"([^"]+)"', filter_str)
        if match:
            query = query.where(User.email == match.group(1))

    # Count
    count_result = await db.execute(query)
    all_users = list(count_result.scalars().all())
    total = len(all_users)

    # Pagination (SCIM is 1-indexed)
    offset = start_index - 1
    result = await db.execute(query.offset(offset).limit(count))
    users = list(result.scalars().all())
    return users, total


async def get_scim_user(
    db: AsyncSession, user_id: uuid.UUID
) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_scim_user(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_name: str,
    display_name: Optional[str] = None,
    external_id: Optional[str] = None,
    active: bool = True,
    password: Optional[str] = None,
) -> User:
    """Create a user via SCIM provisioning."""
    full_name = display_name or user_name
    pwd = password or secrets.token_urlsafe(32)
    user = User(
        email=user_name,
        full_name=full_name,
        hashed_password=hash_password(pwd),
        is_active=active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log_provisioning(
        db, workspace_id, SCIMOperation.create_user,
        "User", str(user.id), SCIMLogStatus.success,
        external_id=external_id,
    )
    return user


async def update_scim_user(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
    user_name: Optional[str] = None,
    display_name: Optional[str] = None,
    active: Optional[bool] = None,
    external_id: Optional[str] = None,
) -> User:
    """Update a user via SCIM."""
    if user_name is not None:
        user.email = user_name
    if display_name is not None:
        user.full_name = display_name
    if active is not None:
        user.is_active = active
    await db.commit()
    await db.refresh(user)

    op = SCIMOperation.update_user
    if active is False:
        op = SCIMOperation.deactivate_user

    await log_provisioning(
        db, workspace_id, op,
        "User", str(user.id), SCIMLogStatus.success,
        external_id=external_id,
    )
    return user


async def deactivate_scim_user(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
) -> User:
    """Deactivate a user via SCIM PATCH."""
    user.is_active = False
    await db.commit()
    await db.refresh(user)

    await log_provisioning(
        db, workspace_id, SCIMOperation.deactivate_user,
        "User", str(user.id), SCIMLogStatus.success,
    )
    return user


# ---------------------------------------------------------------------------
# SCIM Group operations
# ---------------------------------------------------------------------------

async def list_scim_groups(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    start_index: int = 1,
    count: int = 100,
) -> Tuple[List[SCIMGroup], int]:
    """List groups for a workspace."""
    query = (
        select(SCIMGroup)
        .options(selectinload(SCIMGroup.members))
        .where(SCIMGroup.workspace_id == workspace_id)
    )

    count_result = await db.execute(query)
    all_groups = list(count_result.scalars().all())
    total = len(all_groups)

    offset = start_index - 1
    result = await db.execute(query.offset(offset).limit(count))
    groups = list(result.scalars().all())
    return groups, total


async def get_scim_group(
    db: AsyncSession, group_id: uuid.UUID
) -> Optional[SCIMGroup]:
    result = await db.execute(
        select(SCIMGroup)
        .options(selectinload(SCIMGroup.members))
        .where(SCIMGroup.id == group_id)
    )
    return result.scalar_one_or_none()


async def create_scim_group(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    display_name: str,
    external_id: Optional[str] = None,
    member_ids: Optional[List[str]] = None,
) -> SCIMGroup:
    group = SCIMGroup(
        workspace_id=workspace_id,
        display_name=display_name,
        external_id=external_id,
    )
    db.add(group)
    await db.flush()

    # Add members if provided
    if member_ids:
        for mid in member_ids:
            member = SCIMGroupMember(
                group_id=group.id,
                user_id=uuid.UUID(mid),
            )
            db.add(member)

    await db.commit()

    # Reload with members relationship
    result = await db.execute(
        select(SCIMGroup)
        .options(selectinload(SCIMGroup.members))
        .where(SCIMGroup.id == group.id)
    )
    group = result.scalar_one()

    await log_provisioning(
        db, workspace_id, SCIMOperation.create_group,
        "Group", str(group.id), SCIMLogStatus.success,
        external_id=external_id,
    )
    return group


async def update_scim_group(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    group: SCIMGroup,
    display_name: Optional[str] = None,
    external_id: Optional[str] = None,
    member_ids: Optional[List[str]] = None,
) -> SCIMGroup:
    if display_name is not None:
        group.display_name = display_name
    if external_id is not None:
        group.external_id = external_id

    if member_ids is not None:
        # Replace members via the relationship collection so in-memory state
        # and serialized API output stay consistent within the same session.
        group.members = [
            SCIMGroupMember(group_id=group.id, user_id=uuid.UUID(mid))
            for mid in member_ids
        ]

    await db.commit()

    # Reload with members relationship (populate_existing to bypass identity map cache)
    result = await db.execute(
        select(SCIMGroup)
        .options(selectinload(SCIMGroup.members))
        .execution_options(populate_existing=True)
        .where(SCIMGroup.id == group.id)
    )
    group = result.scalar_one()

    await log_provisioning(
        db, workspace_id, SCIMOperation.update_group,
        "Group", str(group.id), SCIMLogStatus.success,
        external_id=group.external_id,
    )
    return group


async def delete_scim_group(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    group: SCIMGroup,
) -> None:
    group_id = str(group.id)
    ext_id = group.external_id
    await db.delete(group)
    await db.commit()

    await log_provisioning(
        db, workspace_id, SCIMOperation.delete_group,
        "Group", group_id, SCIMLogStatus.success,
        external_id=ext_id,
    )


async def add_group_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    group: SCIMGroup,
    user_id: uuid.UUID,
) -> SCIMGroupMember:
    member = SCIMGroupMember(
        group_id=group.id,
        user_id=user_id,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    await log_provisioning(
        db, workspace_id, SCIMOperation.add_member,
        "GroupMember", str(member.id), SCIMLogStatus.success,
    )
    return member


async def remove_group_member(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    group: SCIMGroup,
    user_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(SCIMGroupMember).where(
            SCIMGroupMember.group_id == group.id,
            SCIMGroupMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return False
    member_id = str(member.id)
    await db.delete(member)
    await db.commit()

    await log_provisioning(
        db, workspace_id, SCIMOperation.remove_member,
        "GroupMember", member_id, SCIMLogStatus.success,
    )
    return True


# ---------------------------------------------------------------------------
# Helpers for building SCIM resource dicts
# ---------------------------------------------------------------------------

def user_to_scim_resource(user: User, base_url: str = "") -> Dict[str, Any]:
    """Convert a User model to a SCIM 2.0 User resource dict."""
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "name": {
            "formatted": user.full_name,
        },
        "displayName": user.full_name,
        "emails": [
            {
                "value": user.email,
                "type": "work",
                "primary": True,
            }
        ],
        "active": user.is_active,
        "meta": {
            "resourceType": "User",
            "location": f"{base_url}/scim/v2/Users/{user.id}",
        },
    }


def group_to_scim_resource(group: SCIMGroup, base_url: str = "") -> Dict[str, Any]:
    """Convert a SCIMGroup model to a SCIM 2.0 Group resource dict."""
    members = []
    for m in (group.members or []):
        member_entry: Dict[str, Any] = {"value": str(m.user_id)}
        if m.user:
            member_entry["display"] = m.user.full_name
        members.append(member_entry)

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "id": str(group.id),
        "displayName": group.display_name,
        "externalId": group.external_id,
        "members": members,
        "meta": {
            "resourceType": "Group",
            "location": f"{base_url}/scim/v2/Groups/{group.id}",
        },
    }
