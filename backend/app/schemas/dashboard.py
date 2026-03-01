import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.dashboard import WidgetType


# ── Widget schemas ────────────────────────────────────────────────────────────

class DashboardWidgetCreate(BaseModel):
    widget_type: WidgetType
    title: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    position_x: int = 0
    position_y: int = 0
    width: int = 6
    height: int = 4
    sort_order: int = 0


class DashboardWidgetUpdate(BaseModel):
    title: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sort_order: Optional[int] = None


class DashboardWidgetResponse(BaseModel):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    widget_type: WidgetType
    title: Optional[str]
    config: Optional[Dict[str, Any]]
    position_x: int
    position_y: int
    width: int
    height: int
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard schemas ─────────────────────────────────────────────────────────

class DashboardCreate(BaseModel):
    name: str
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None


class DashboardUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_published: Optional[bool] = None
    layout: Optional[Dict[str, Any]] = None


class DashboardResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    model_id: uuid.UUID
    owner_id: uuid.UUID
    is_published: bool
    layout: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardWithWidgetsResponse(DashboardResponse):
    widgets: List[DashboardWidgetResponse] = []
