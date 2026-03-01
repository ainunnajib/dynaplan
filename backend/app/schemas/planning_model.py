import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class PlanningModelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    workspace_id: uuid.UUID
    settings: Optional[dict[str, Any]] = None


class PlanningModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class PlanningModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    workspace_id: uuid.UUID
    owner_id: uuid.UUID
    is_archived: bool
    settings: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanningModelClone(BaseModel):
    name: str
    workspace_id: Optional[uuid.UUID] = None
