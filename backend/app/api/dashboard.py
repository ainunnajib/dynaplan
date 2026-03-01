import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardResponse,
    DashboardUpdate,
    DashboardWithWidgetsResponse,
    DashboardWidgetCreate,
    DashboardWidgetResponse,
    DashboardWidgetUpdate,
)
from app.services.dashboard import (
    create_dashboard,
    create_widget,
    delete_dashboard,
    delete_widget,
    get_dashboard_by_id,
    get_widget_by_id,
    list_dashboards_for_model,
    update_dashboard,
    update_widget,
)

router = APIRouter(tags=["dashboards"])


# ── Dependency helpers ────────────────────────────────────────────────────────

async def _get_owned_dashboard(
    dashboard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = await get_dashboard_by_id(db, dashboard_id)
    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found",
        )
    if dashboard.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this dashboard",
        )
    return dashboard


async def _get_owned_widget(
    widget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    widget = await get_widget_by_id(db, widget_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )
    # Check that the parent dashboard belongs to current user
    dashboard = await get_dashboard_by_id(db, widget.dashboard_id)
    if dashboard is None or dashboard.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this widget",
        )
    return widget


# ── Dashboard routes ──────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/dashboards",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard_route(
    model_id: uuid.UUID,
    data: DashboardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dashboard = await create_dashboard(db, data, model_id=model_id, owner_id=current_user.id)
    return dashboard


@router.get(
    "/models/{model_id}/dashboards",
    response_model=List[DashboardResponse],
)
async def list_dashboards_route(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_dashboards_for_model(db, model_id=model_id, owner_id=current_user.id)


@router.get(
    "/dashboards/{dashboard_id}",
    response_model=DashboardWithWidgetsResponse,
)
async def get_dashboard_route(
    dashboard=Depends(_get_owned_dashboard),
):
    return dashboard


@router.patch(
    "/dashboards/{dashboard_id}",
    response_model=DashboardResponse,
)
async def update_dashboard_route(
    data: DashboardUpdate,
    dashboard=Depends(_get_owned_dashboard),
    db: AsyncSession = Depends(get_db),
):
    return await update_dashboard(db, dashboard, data)


@router.delete(
    "/dashboards/{dashboard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dashboard_route(
    dashboard=Depends(_get_owned_dashboard),
    db: AsyncSession = Depends(get_db),
):
    await delete_dashboard(db, dashboard)


# ── Widget routes ─────────────────────────────────────────────────────────────

@router.post(
    "/dashboards/{dashboard_id}/widgets",
    response_model=DashboardWidgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_widget_route(
    data: DashboardWidgetCreate,
    dashboard=Depends(_get_owned_dashboard),
    db: AsyncSession = Depends(get_db),
):
    widget = await create_widget(db, data, dashboard_id=dashboard.id)
    return widget


@router.patch(
    "/widgets/{widget_id}",
    response_model=DashboardWidgetResponse,
)
async def update_widget_route(
    data: DashboardWidgetUpdate,
    widget=Depends(_get_owned_widget),
    db: AsyncSession = Depends(get_db),
):
    return await update_widget(db, widget, data)


@router.delete(
    "/widgets/{widget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_widget_route(
    widget=Depends(_get_owned_widget),
    db: AsyncSession = Depends(get_db),
):
    await delete_widget(db, widget)
