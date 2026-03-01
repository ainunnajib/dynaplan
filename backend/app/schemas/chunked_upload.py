import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.chunked_upload import (
    BatchStatus,
    ImportTaskStatus,
    ImportTaskType,
    UploadStatus,
)


# ── Chunked Upload schemas ─────────────────────────────────────────────────────

class ChunkedUploadCreate(BaseModel):
    filename: str
    content_type: str
    total_chunks: int
    total_size_bytes: Optional[int] = None


class ChunkUploadRequest(BaseModel):
    chunk_index: int
    data: str  # base64-encoded chunk data
    size_bytes: int
    checksum: Optional[str] = None


class ChunkResponse(BaseModel):
    id: uuid.UUID
    upload_id: uuid.UUID
    chunk_index: int
    size_bytes: int
    checksum: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkedUploadResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    filename: str
    content_type: str
    total_chunks: int
    received_chunks: int
    total_size_bytes: Optional[int] = None
    status: UploadStatus
    created_by: uuid.UUID
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Import Task schemas ───────────────────────────────────────────────────────

class ImportTaskCreate(BaseModel):
    upload_id: Optional[uuid.UUID] = None
    task_type: ImportTaskType
    target_id: str
    total_records: Optional[int] = None


class ImportTaskResponse(BaseModel):
    id: uuid.UUID
    upload_id: Optional[uuid.UUID] = None
    model_id: uuid.UUID
    task_type: ImportTaskType
    target_id: str
    status: ImportTaskStatus
    total_records: Optional[int] = None
    processed_records: int
    error_count: int
    errors: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Transactional Batch schemas ────────────────────────────────────────────────

class TransactionalBatchCreate(BaseModel):
    pass  # model_id comes from the URL path


class BatchOperationRequest(BaseModel):
    operation_type: str  # e.g., "write_cell", "delete_cell", "update_item"
    target: str  # target identifier (line_item_id, dimension_id, etc.)
    payload: Dict[str, Any]


class TransactionalBatchResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    status: BatchStatus
    operations: Optional[List[Dict[str, Any]]] = None
    created_by: uuid.UUID
    created_at: datetime
    committed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
