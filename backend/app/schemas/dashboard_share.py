import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.dashboard_share import SharePermission


# ---------------------------------------------------------------------------
# DashboardShare schemas
# ---------------------------------------------------------------------------

class DashboardShareCreate(BaseModel):
    user_email: str
    permission: SharePermission = SharePermission.view


class DashboardShareResponse(BaseModel):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    shared_with_user_id: uuid.UUID
    permission: SharePermission
    shared_by_user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# DashboardContextFilter schemas
# ---------------------------------------------------------------------------

class ContextFilterItem(BaseModel):
    dimension_id: uuid.UUID
    selected_member_ids: List[uuid.UUID] = []
    label: Optional[str] = None


class ContextFiltersSave(BaseModel):
    filters: List[ContextFilterItem]


class ContextFilterResponse(BaseModel):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    dimension_id: uuid.UUID
    selected_member_ids: List[uuid.UUID]
    label: Optional[str]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Shared dashboard listing
# ---------------------------------------------------------------------------

class SharedDashboardResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    model_id: uuid.UUID
    owner_id: uuid.UUID
    is_published: bool
    permission: SharePermission
    shared_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
