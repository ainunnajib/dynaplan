import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class StageCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_gate: bool = False


class StageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_gate: Optional[bool] = None


class StageResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    name: str
    description: Optional[str]
    sort_order: int
    is_gate: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    stage_id: uuid.UUID
    name: str
    description: Optional[str]
    assignee_id: Optional[uuid.UUID]
    status: str
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

class ApprovalCreate(BaseModel):
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    approver_id: uuid.UUID
    decision: str
    comment: Optional[str]
    decided_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Composite responses
# ---------------------------------------------------------------------------

class StageWithTasks(StageResponse):
    tasks: List[TaskResponse] = []


class WorkflowDetail(WorkflowResponse):
    stages: List[StageWithTasks] = []


class WorkflowProgress(BaseModel):
    workflow_id: uuid.UUID
    workflow_name: str
    status: str
    total_stages: int
    total_tasks: int
    tasks_by_status: dict
    gate_stages_completed: int
    gate_stages_total: int
