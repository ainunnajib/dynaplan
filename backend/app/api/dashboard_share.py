import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard_share import (
    ContextFilterResponse,
    ContextFiltersSave,
    DashboardShareCreate,
    DashboardShareResponse,
    SharedDashboardResponse,
)
from app.services.dashboard_share import (
    can_access_dashboard,
    get_context_filters,
    get_dashboard_by_id,
    get_shared_dashboards,
    get_user_by_email,
    publish_dashboard,
    save_context_filters,
    share_dashboard,
    unpublish_dashboard,
    unshare_dashboard,
)

router = APIRouter(prefix="/dashboards", tags=["dashboard-sharing"])


async def _require_dashboard_owner(
    dashboard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dependency: load dashboard and assert current user is the owner."""
    dashboard = await get_dashboard_by_id(db, dashboard_id)
    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found",
        )
    if dashboard.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this dashboard",
        )
    return dashboard


# ---------------------------------------------------------------------------
# Publish / unpublish
# ---------------------------------------------------------------------------

@router.post("/{dashboard_id}/publish", status_code=status.HTTP_200_OK)
async def publish(
    dashboard=Depends(_require_dashboard_owner),
    db: AsyncSession = Depends(get_db),
):
    """Publish a dashboard so any authenticated user can view it."""
    updated = await publish_dashboard(db, dashboard.id)
    return {"id": str(updated.id), "is_published": updated.is_published}


@router.post("/{dashboard_id}/unpublish", status_code=status.HTTP_200_OK)
async def unpublish(
    dashboard=Depends(_require_dashboard_owner),
    db: AsyncSession = Depends(get_db),
):
    """Unpublish a dashboard — removes public access."""
    updated = await unpublish_dashboard(db, dashboard.id)
    return {"id": str(updated.id), "is_published": updated.is_published}


# ---------------------------------------------------------------------------
# Share / unshare
# ---------------------------------------------------------------------------

@router.post(
    "/{dashboard_id}/share",
    response_model=DashboardShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def share(
    data: DashboardShareCreate,
    dashboard=Depends(_require_dashboard_owner),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Share a dashboard with another user by email."""
    target_user = await get_user_by_email(db, data.user_email)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{data.user_email}' not found",
        )
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot share a dashboard with yourself",
        )
    share_record = await share_dashboard(
        db,
        dashboard_id=dashboard.id,
        user_id=target_user.id,
        permission=data.permission,
        shared_by=current_user.id,
    )
    return share_record


@router.delete(
    "/{dashboard_id}/share/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unshare(
    user_id: uuid.UUID,
    dashboard=Depends(_require_dashboard_owner),
    db: AsyncSession = Depends(get_db),
):
    """Remove a user's access to a dashboard."""
    removed = await unshare_dashboard(db, dashboard_id=dashboard.id, user_id=user_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share record not found",
        )


# ---------------------------------------------------------------------------
# List dashboards shared with me
# ---------------------------------------------------------------------------

@router.get(
    "/shared-with-me",
    response_model=List[SharedDashboardResponse],
    status_code=status.HTTP_200_OK,
)
async def list_shared_with_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all dashboards that have been explicitly shared with the current user."""
    rows = await get_shared_dashboards(db, user_id=current_user.id)
    return rows


# ---------------------------------------------------------------------------
# Context filters
# ---------------------------------------------------------------------------

@router.post(
    "/{dashboard_id}/context-filters",
    response_model=List[ContextFilterResponse],
    status_code=status.HTTP_200_OK,
)
async def save_filters(
    data: ContextFiltersSave,
    dashboard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save (replace) context filters for a dashboard. User must have access."""
    accessible = await can_access_dashboard(db, dashboard_id, current_user.id)
    if not accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this dashboard",
        )
    filters = await save_context_filters(db, dashboard_id, data.filters)
    return filters


@router.get(
    "/{dashboard_id}/context-filters",
    response_model=List[ContextFilterResponse],
    status_code=status.HTTP_200_OK,
)
async def get_filters(
    dashboard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve saved context filters for a dashboard. User must have access."""
    accessible = await can_access_dashboard(db, dashboard_id, current_user.id)
    if not accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this dashboard",
        )
    filters = await get_context_filters(db, dashboard_id)
    return filters
