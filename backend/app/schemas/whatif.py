import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ── Scenario schemas ────────────────────────────────────────────────────────────

class ScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    base_version_id: Optional[uuid.UUID] = None


class ScenarioResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    description: Optional[str]
    base_version_id: Optional[uuid.UUID]
    created_by: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    assumption_count: int = 0

    model_config = {"from_attributes": True}


# ── Assumption schemas ──────────────────────────────────────────────────────────

class AssumptionCreate(BaseModel):
    line_item_id: uuid.UUID
    dimension_key: str
    modified_value: str
    note: Optional[str] = None


class AssumptionResponse(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    line_item_id: uuid.UUID
    dimension_key: str
    original_value: Optional[str]
    modified_value: str
    note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Evaluation / comparison schemas ────────────────────────────────────────────

class EvaluatedCell(BaseModel):
    line_item_id: uuid.UUID
    dimension_key: str
    value: Optional[str]
    is_modified: bool


class ScenarioEvalResult(BaseModel):
    scenario_id: uuid.UUID
    cells: List[EvaluatedCell]


class DiffCell(BaseModel):
    line_item_id: uuid.UUID
    dimension_key: str
    original_value: Optional[str]
    modified_value: str


class ScenarioCompareResult(BaseModel):
    scenario_id: uuid.UUID
    diffs: List[DiffCell]
