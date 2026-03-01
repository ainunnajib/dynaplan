import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.bulk_job import BulkJobStatus, BulkJobType


# ── Cell input schema ───────────────────────────────────────────────────────────

class CellInput(BaseModel):
    line_item_id: uuid.UUID
    dimension_members: List[uuid.UUID]
    value: Any


# ── Request schemas ─────────────────────────────────────────────────────────────

class BulkWriteRequest(BaseModel):
    cells: List[CellInput]
    chunk_size: Optional[int] = 100


class BulkReadRequest(BaseModel):
    line_item_ids: Optional[List[uuid.UUID]] = None
    dimension_filters: Optional[Dict[str, List[uuid.UUID]]] = None
    limit: int = 1000
    offset: int = 0


class BulkDeleteRequest(BaseModel):
    line_item_id: Optional[uuid.UUID] = None
    dimension_key_prefix: Optional[str] = None


class BulkCopyRequest(BaseModel):
    source_model_id: uuid.UUID
    target_model_id: uuid.UUID
    line_item_mapping: Dict[str, str]  # source line_item_id -> target line_item_id


# ── Response schemas ────────────────────────────────────────────────────────────

class BulkJobResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    job_type: BulkJobType
    status: BulkJobStatus
    total_rows: Optional[int] = None
    processed_rows: int
    failed_rows: int
    error_message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    result_summary: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BulkJobProgress(BaseModel):
    job_id: uuid.UUID
    status: BulkJobStatus
    processed_rows: int
    total_rows: Optional[int] = None
    failed_rows: int
    percentage: Optional[float] = None

    model_config = {"from_attributes": True}


class BulkCellRead(BaseModel):
    line_item_id: uuid.UUID
    dimension_key: str
    dimension_members: List[uuid.UUID]
    value: Any
    value_type: str

    model_config = {"from_attributes": True}


class BulkReadResponse(BaseModel):
    cells: List[BulkCellRead]
    total_count: int
    has_more: bool
