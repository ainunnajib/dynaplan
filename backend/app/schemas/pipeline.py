import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PipelineResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# PipelineStep
# ---------------------------------------------------------------------------


class PipelineStepCreate(BaseModel):
    name: str
    step_type: str
    config: Optional[str] = None
    sort_order: int = 0


class PipelineStepUpdate(BaseModel):
    name: Optional[str] = None
    step_type: Optional[str] = None
    config: Optional[str] = None
    sort_order: Optional[int] = None


class PipelineStepResponse(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    name: str
    step_type: str
    config: Optional[str]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StepReorderItem(BaseModel):
    step_id: uuid.UUID
    sort_order: int


class StepReorderRequest(BaseModel):
    steps: List[StepReorderItem]


# ---------------------------------------------------------------------------
# PipelineRun
# ---------------------------------------------------------------------------


class PipelineRunResponse(BaseModel):
    id: uuid.UUID
    pipeline_id: uuid.UUID
    status: str
    triggered_by: uuid.UUID
    total_steps: int
    completed_steps: int
    error_step_id: Optional[uuid.UUID]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# PipelineStepLog
# ---------------------------------------------------------------------------


class PipelineStepLogResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    status: str
    records_in: Optional[int]
    records_out: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    log_output: Optional[str]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Composite responses
# ---------------------------------------------------------------------------


class PipelineWithSteps(PipelineResponse):
    steps: List[PipelineStepResponse] = []


class PipelineRunDetail(PipelineRunResponse):
    step_logs: List[PipelineStepLogResponse] = []


class PipelineValidationResult(BaseModel):
    valid: bool
    errors: List[str] = []
