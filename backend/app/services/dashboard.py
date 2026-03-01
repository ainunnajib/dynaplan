import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dashboard import Dashboard, DashboardWidget
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    DashboardWidgetCreate,
    DashboardWidgetUpdate,
)


# ── Dashboard CRUD ────────────────────────────────────────────────────────────

async def create_dashboard(
    db: AsyncSession,
    data: DashboardCreate,
    model_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Dashboard:
    dashboard = Dashboard(
        name=data.name,
        description=data.description,
        model_id=model_id,
        owner_id=owner_id,
        layout=data.layout or {},
    )
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)
    return dashboard


async def get_dashboard_by_id(
    db: AsyncSession, dashboard_id: uuid.UUID
) -> Optional[Dashboard]:
    result = await db.execute(
        select(Dashboard)
        .where(Dashboard.id == dashboard_id)
        .options(selectinload(Dashboard.widgets))
    )
    return result.scalar_one_or_none()


async def list_dashboards_for_model(
    db: AsyncSession, model_id: uuid.UUID, owner_id: uuid.UUID
) -> List[Dashboard]:
    result = await db.execute(
        select(Dashboard)
        .where(Dashboard.model_id == model_id, Dashboard.owner_id == owner_id)
        .order_by(Dashboard.created_at)
    )
    return list(result.scalars().all())


async def update_dashboard(
    db: AsyncSession, dashboard: Dashboard, data: DashboardUpdate
) -> Dashboard:
    if data.name is not None:
        dashboard.name = data.name
    if data.description is not None:
        dashboard.description = data.description
    if data.is_published is not None:
        dashboard.is_published = data.is_published
    if data.layout is not None:
        dashboard.layout = data.layout
    await db.commit()
    await db.refresh(dashboard)
    return dashboard


async def delete_dashboard(db: AsyncSession, dashboard: Dashboard) -> None:
    await db.delete(dashboard)
    await db.commit()


# ── Widget CRUD ───────────────────────────────────────────────────────────────

async def create_widget(
    db: AsyncSession,
    data: DashboardWidgetCreate,
    dashboard_id: uuid.UUID,
) -> DashboardWidget:
    widget = DashboardWidget(
        dashboard_id=dashboard_id,
        widget_type=data.widget_type,
        title=data.title,
        config=data.config or {},
        position_x=data.position_x,
        position_y=data.position_y,
        width=data.width,
        height=data.height,
        sort_order=data.sort_order,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def get_widget_by_id(
    db: AsyncSession, widget_id: uuid.UUID
) -> Optional[DashboardWidget]:
    result = await db.execute(
        select(DashboardWidget).where(DashboardWidget.id == widget_id)
    )
    return result.scalar_one_or_none()


async def update_widget(
    db: AsyncSession, widget: DashboardWidget, data: DashboardWidgetUpdate
) -> DashboardWidget:
    if data.title is not None:
        widget.title = data.title
    if data.config is not None:
        widget.config = data.config
    if data.position_x is not None:
        widget.position_x = data.position_x
    if data.position_y is not None:
        widget.position_y = data.position_y
    if data.width is not None:
        widget.width = data.width
    if data.height is not None:
        widget.height = data.height
    if data.sort_order is not None:
        widget.sort_order = data.sort_order
    await db.commit()
    await db.refresh(widget)
    return widget


async def delete_widget(db: AsyncSession, widget: DashboardWidget) -> None:
    await db.delete(widget)
    await db.commit()


async def reorder_widgets(
    db: AsyncSession,
    dashboard_id: uuid.UUID,
    widget_ids: List[uuid.UUID],
) -> List[DashboardWidget]:
    """Assign sort_order based on the position in the provided widget_ids list."""
    result = await db.execute(
        select(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard_id)
    )
    widgets = {w.id: w for w in result.scalars().all()}

    for order, wid in enumerate(widget_ids):
        if wid in widgets:
            widgets[wid].sort_order = order

    await db.commit()
    updated = list(widgets.values())
    updated.sort(key=lambda w: w.sort_order)
    return updated
