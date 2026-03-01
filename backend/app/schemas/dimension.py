import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.dimension import DimensionType


# ── Dimension schemas ──────────────────────────────────────────────────────────

class DimensionCreate(BaseModel):
    name: str
    dimension_type: DimensionType = DimensionType.custom


class DimensionUpdate(BaseModel):
    name: Optional[str] = None
    dimension_type: Optional[DimensionType] = None


class DimensionResponse(BaseModel):
    id: uuid.UUID
    name: str
    dimension_type: DimensionType
    model_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── DimensionItem schemas ──────────────────────────────────────────────────────

class DimensionItemCreate(BaseModel):
    name: str
    code: str
    parent_id: Optional[uuid.UUID] = None
    sort_order: int = 0


class DimensionItemUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    sort_order: Optional[int] = None


class DimensionItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    dimension_id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DimensionItemNode(BaseModel):
    """A dimension item with its children — used for tree responses."""
    id: uuid.UUID
    name: str
    code: str
    dimension_id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    sort_order: int
    created_at: datetime
    updated_at: datetime
    children: List["DimensionItemNode"] = []

    model_config = {"from_attributes": True}


# Allow forward reference resolution
DimensionItemNode.model_rebuild()
