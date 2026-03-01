import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.module import LineItemFormat, SummaryMethod


# ── Module schemas ─────────────────────────────────────────────────────────────

class ModuleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ModuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ModuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    model_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModuleWithLineItemsResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    model_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    line_items: List["LineItemResponse"] = []

    model_config = {"from_attributes": True}


# ── LineItem schemas ───────────────────────────────────────────────────────────

class LineItemCreate(BaseModel):
    name: str
    format: LineItemFormat = LineItemFormat.number
    formula: Optional[str] = None
    summary_method: SummaryMethod = SummaryMethod.sum
    applies_to_dimensions: Optional[List[uuid.UUID]] = None
    sort_order: int = 0


class LineItemUpdate(BaseModel):
    name: Optional[str] = None
    format: Optional[LineItemFormat] = None
    formula: Optional[str] = None
    summary_method: Optional[SummaryMethod] = None
    applies_to_dimensions: Optional[List[uuid.UUID]] = None
    sort_order: Optional[int] = None


class LineItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    module_id: uuid.UUID
    format: LineItemFormat
    formula: Optional[str]
    summary_method: SummaryMethod
    applies_to_dimensions: Optional[List[uuid.UUID]]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Allow forward reference resolution
ModuleWithLineItemsResponse.model_rebuild()
