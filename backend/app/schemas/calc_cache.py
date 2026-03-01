import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CacheEntryResponse(BaseModel):
    id: uuid.UUID
    line_item_id: uuid.UUID
    dimension_key: str
    computed_value: Optional[str]
    formula_hash: Optional[str]
    is_valid: bool
    computed_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CacheStats(BaseModel):
    total_entries: int
    valid_count: int
    invalid_count: int
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class InvalidateRequest(BaseModel):
    line_item_id: uuid.UUID
    dimension_key: Optional[str] = None
    cascade: bool = True


class RecalcResult(BaseModel):
    entries_recalculated: int
    entries_remaining: int
