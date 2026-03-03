import uuid
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel

from app.models.cloudworks import ConnectorType, RunStatus, ScheduleType


# ---------------------------------------------------------------------------
# Connection schemas
# ---------------------------------------------------------------------------

class ConnectionCreate(BaseModel):
    name: str
    connector_type: ConnectorType
    config: Optional[Dict] = None
    is_active: Optional[bool] = True


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    connector_type: Optional[ConnectorType] = None
    config: Optional[Dict] = None
    is_active: Optional[bool] = None


class ConnectionResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    connector_type: ConnectorType
    config: Optional[Dict]
    is_active: bool
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schedule schemas
# ---------------------------------------------------------------------------

class ScheduleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    schedule_type: ScheduleType
    cron_expression: str
    source_config: Optional[Dict] = None
    target_config: Optional[Dict] = None
    is_enabled: Optional[bool] = True
    max_retries: Optional[int] = 3
    retry_delay_seconds: Optional[int] = 60


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schedule_type: Optional[ScheduleType] = None
    cron_expression: Optional[str] = None
    source_config: Optional[Dict] = None
    target_config: Optional[Dict] = None
    max_retries: Optional[int] = None
    retry_delay_seconds: Optional[int] = None


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    name: str
    description: Optional[str]
    schedule_type: ScheduleType
    cron_expression: str
    source_config: Optional[Dict]
    target_config: Optional[Dict]
    is_enabled: bool
    max_retries: int
    retry_delay_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleEnableRequest(BaseModel):
    is_enabled: bool


class ScheduleStatusResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_enabled: bool
    last_run_status: Optional[RunStatus] = None
    last_run_at: Optional[datetime] = None
    total_runs: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Run schemas
# ---------------------------------------------------------------------------

class RunResponse(BaseModel):
    id: uuid.UUID
    schedule_id: uuid.UUID
    status: RunStatus
    attempt_number: int
    records_processed: Optional[int]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class RunTriggerResponse(BaseModel):
    id: uuid.UUID
    schedule_id: uuid.UUID
    status: RunStatus
    attempt_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCompleteRequest(BaseModel):
    records_processed: Optional[int] = None


class RunFailRequest(BaseModel):
    error_message: Optional[str] = None
