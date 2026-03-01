import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.models.action import ActionType, ProcessStatus


# ---------------------------------------------------------------------------
# Action schemas
# ---------------------------------------------------------------------------

class ActionCreate(BaseModel):
    name: str
    action_type: ActionType
    config: Optional[Dict] = None


class ActionUpdate(BaseModel):
    name: Optional[str] = None
    action_type: Optional[ActionType] = None
    config: Optional[Dict] = None


class ActionResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_id: uuid.UUID
    action_type: ActionType
    config: Optional[Dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Process schemas
# ---------------------------------------------------------------------------

class ProcessCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProcessStepResponse(BaseModel):
    id: uuid.UUID
    process_id: uuid.UUID
    action_id: uuid.UUID
    step_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProcessResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_id: uuid.UUID
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcessWithStepsResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_id: uuid.UUID
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    steps: List[ProcessStepResponse]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ProcessStep schemas
# ---------------------------------------------------------------------------

class ProcessStepCreate(BaseModel):
    action_id: uuid.UUID
    step_order: int


# ---------------------------------------------------------------------------
# ProcessRun schemas
# ---------------------------------------------------------------------------

class ProcessRunResponse(BaseModel):
    id: uuid.UUID
    process_id: uuid.UUID
    status: ProcessStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[Dict]
    triggered_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}
