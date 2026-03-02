import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Write schemas ──────────────────────────────────────────────────────────────

class CellWrite(BaseModel):
    line_item_id: uuid.UUID
    dimension_members: List[uuid.UUID]
    version_id: Optional[uuid.UUID] = None
    value: Any  # number, string, or boolean


class CellBulkWrite(BaseModel):
    cells: List[CellWrite]


# ── Read schemas ───────────────────────────────────────────────────────────────

class CellRead(BaseModel):
    line_item_id: uuid.UUID
    dimension_members: List[uuid.UUID]
    version_id: Optional[uuid.UUID] = None
    dimension_key: str
    value: Any
    value_type: str  # "number", "text", "boolean", or "null"

    model_config = {"from_attributes": True}


# ── Query schema ───────────────────────────────────────────────────────────────

class CellQuery(BaseModel):
    line_item_id: uuid.UUID
    version_id: Optional[uuid.UUID] = None
    dimension_filters: Optional[Dict[str, List[uuid.UUID]]] = None


# ── Legacy module-grid compatibility schemas ──────────────────────────────────

class ModuleCellRead(BaseModel):
    line_item_id: uuid.UUID
    dimension_member_ids: List[uuid.UUID]
    value: Any


class ModuleCellWrite(BaseModel):
    line_item_id: uuid.UUID
    dimension_member_ids: List[uuid.UUID]
    value: Any


class ModuleCellPageResponse(BaseModel):
    cells: List[ModuleCellRead]
    total_count: int
    offset: int
    limit: int
    has_more: bool
