import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Write schemas ──────────────────────────────────────────────────────────────

class CellWrite(BaseModel):
    line_item_id: uuid.UUID
    dimension_members: List[uuid.UUID]
    value: Any  # number, string, or boolean


class CellBulkWrite(BaseModel):
    cells: List[CellWrite]


# ── Read schemas ───────────────────────────────────────────────────────────────

class CellRead(BaseModel):
    line_item_id: uuid.UUID
    dimension_members: List[uuid.UUID]
    dimension_key: str
    value: Any
    value_type: str  # "number", "text", "boolean", or "null"

    model_config = {"from_attributes": True}


# ── Query schema ───────────────────────────────────────────────────────────────

class CellQuery(BaseModel):
    line_item_id: uuid.UUID
    dimension_filters: Optional[Dict[str, List[uuid.UUID]]] = None
