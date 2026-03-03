"""
Pydantic schemas for F025: Top-down & bottom-up planning.
"""
import uuid
from typing import List, Optional

from pydantic import BaseModel

from app.engine.spread import SpreadMethod


# ── Request schemas ────────────────────────────────────────────────────────────

class SpreadRequest(BaseModel):
    line_item_id: uuid.UUID
    parent_member_id: uuid.UUID
    target_value: float
    method: SpreadMethod
    weights: Optional[List[float]] = None


class AggregateRequest(BaseModel):
    line_item_id: uuid.UUID
    parent_member_id: uuid.UUID


class BulkSpreadRequest(BaseModel):
    spreads: List[SpreadRequest]


class RecalculateHierarchyRequest(BaseModel):
    line_item_id: uuid.UUID
    dimension_id: uuid.UUID


# ── Response schemas ───────────────────────────────────────────────────────────

class MemberValue(BaseModel):
    member_id: uuid.UUID
    value: float


class SpreadResponse(BaseModel):
    line_item_id: uuid.UUID
    cells_updated: List[MemberValue]


class AggregateResponse(BaseModel):
    parent_value: float
    children_values: List[MemberValue]


class HierarchyMemberValue(BaseModel):
    member_id: uuid.UUID
    member_name: str
    value: float
    is_parent: bool


class HierarchyValuesResponse(BaseModel):
    line_item_id: uuid.UUID
    parent_member_id: Optional[uuid.UUID]
    parent_value: Optional[float]
    children: List[HierarchyMemberValue]


class BulkSpreadResponse(BaseModel):
    results: List[SpreadResponse]


class RecalculateHierarchyResponse(BaseModel):
    line_item_id: uuid.UUID
    dimension_id: uuid.UUID
    members_updated: int
