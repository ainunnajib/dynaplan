import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.observability import (
    GrafanaDashboardTemplateResponse,
    ObservabilityDashboardResponse,
)
from app.services.observability import (
    build_observability_dashboard,
    get_grafana_dashboard_template,
    render_prometheus_metrics,
)

router = APIRouter(tags=["observability"])


@router.get(
    "/observability/dashboard",
    response_model=ObservabilityDashboardResponse,
)
async def get_observability_dashboard(
    model_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ObservabilityDashboardResponse:
    _ = current_user
    payload = await build_observability_dashboard(db, model_id=model_id)
    return ObservabilityDashboardResponse.model_validate(payload)


@router.get(
    "/observability/grafana-template",
    response_model=GrafanaDashboardTemplateResponse,
)
async def get_grafana_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GrafanaDashboardTemplateResponse:
    _ = db
    _ = current_user
    template = get_grafana_dashboard_template()
    title = str(template.get("title") or "Dynaplan Observability")
    return GrafanaDashboardTemplateResponse(title=title, template=template)


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def prometheus_metrics(
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    payload = await render_prometheus_metrics(db)
    return PlainTextResponse(
        content=payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
