import uuid
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import Dashboard
from app.models.dashboard_share import DashboardContextFilter, DashboardShare, SharePermission
from app.models.user import User
from app.schemas.dashboard_share import ContextFilterItem


async def publish_dashboard(db: AsyncSession, dashboard_id: uuid.UUID) -> Optional[Dashboard]:
    """Set is_published=True on the dashboard."""
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        return None
    dashboard.is_published = True
    await db.commit()
    await db.refresh(dashboard)
    return dashboard


async def unpublish_dashboard(db: AsyncSession, dashboard_id: uuid.UUID) -> Optional[Dashboard]:
    """Set is_published=False on the dashboard."""
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        return None
    dashboard.is_published = False
    await db.commit()
    await db.refresh(dashboard)
    return dashboard


async def share_dashboard(
    db: AsyncSession,
    dashboard_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: SharePermission,
    shared_by: uuid.UUID,
) -> Optional[DashboardShare]:
    """Create or update a share record for (dashboard_id, user_id)."""
    # Check if share already exists
    result = await db.execute(
        select(DashboardShare).where(
            DashboardShare.dashboard_id == dashboard_id,
            DashboardShare.shared_with_user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.permission = permission
        existing.shared_by_user_id = shared_by
        await db.commit()
        await db.refresh(existing)
        return existing

    share = DashboardShare(
        dashboard_id=dashboard_id,
        shared_with_user_id=user_id,
        permission=permission,
        shared_by_user_id=shared_by,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share


async def unshare_dashboard(
    db: AsyncSession,
    dashboard_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Remove a share record. Returns True if a record was deleted, False otherwise."""
    result = await db.execute(
        select(DashboardShare).where(
            DashboardShare.dashboard_id == dashboard_id,
            DashboardShare.shared_with_user_id == user_id,
        )
    )
    share = result.scalar_one_or_none()
    if share is None:
        return False
    await db.delete(share)
    await db.commit()
    return True


async def get_shared_dashboards(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[dict]:
    """Return dashboards shared with this user, including the share permission."""
    result = await db.execute(
        select(DashboardShare, Dashboard)
        .join(Dashboard, DashboardShare.dashboard_id == Dashboard.id)
        .where(DashboardShare.shared_with_user_id == user_id)
    )
    rows = result.all()
    output = []
    for share, dashboard in rows:
        output.append({
            "id": dashboard.id,
            "name": dashboard.name,
            "description": dashboard.description,
            "model_id": dashboard.model_id,
            "owner_id": dashboard.owner_id,
            "is_published": dashboard.is_published,
            "permission": share.permission,
            "shared_by_user_id": share.shared_by_user_id,
            "created_at": dashboard.created_at,
            "updated_at": dashboard.updated_at,
        })
    return output


async def can_access_dashboard(
    db: AsyncSession,
    dashboard_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Check whether user can access the dashboard: owner, shared, or published."""
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        return False
    # Owner always has access
    if dashboard.owner_id == user_id:
        return True
    # Published dashboards are accessible to anyone
    if dashboard.is_published:
        return True
    # Check if explicitly shared
    share_result = await db.execute(
        select(DashboardShare).where(
            DashboardShare.dashboard_id == dashboard_id,
            DashboardShare.shared_with_user_id == user_id,
        )
    )
    share = share_result.scalar_one_or_none()
    return share is not None


async def save_context_filters(
    db: AsyncSession,
    dashboard_id: uuid.UUID,
    filters: List[ContextFilterItem],
) -> List[DashboardContextFilter]:
    """Replace all context filters for a dashboard."""
    # Delete existing filters for this dashboard
    await db.execute(
        delete(DashboardContextFilter).where(
            DashboardContextFilter.dashboard_id == dashboard_id
        )
    )
    await db.flush()

    new_filters = []
    for f in filters:
        cf = DashboardContextFilter(
            dashboard_id=dashboard_id,
            dimension_id=f.dimension_id,
            selected_member_ids=[str(mid) for mid in f.selected_member_ids],
            label=f.label,
        )
        db.add(cf)
        new_filters.append(cf)

    await db.commit()
    for cf in new_filters:
        await db.refresh(cf)
    return new_filters


async def get_context_filters(
    db: AsyncSession,
    dashboard_id: uuid.UUID,
) -> List[DashboardContextFilter]:
    """Load saved context filters for a dashboard."""
    result = await db.execute(
        select(DashboardContextFilter).where(
            DashboardContextFilter.dashboard_id == dashboard_id
        )
    )
    return list(result.scalars().all())


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Look up a user by email (for sharing by email address)."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_dashboard_by_id(
    db: AsyncSession, dashboard_id: uuid.UUID
) -> Optional[Dashboard]:
    """Fetch a dashboard by its primary key."""
    result = await db.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    return result.scalar_one_or_none()
