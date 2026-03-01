import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, LargeBinary, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class UploadStatus(str, enum.Enum):
    uploading = "uploading"
    complete = "complete"
    failed = "failed"
    expired = "expired"


class ImportTaskType(str, enum.Enum):
    list_import = "list_import"
    module_import = "module_import"
    cell_import = "cell_import"


class ImportTaskStatus(str, enum.Enum):
    pending = "pending"
    validating = "validating"
    importing = "importing"
    completed = "completed"
    failed = "failed"


class BatchStatus(str, enum.Enum):
    open = "open"
    committed = "committed"
    rolled_back = "rolled_back"
    expired = "expired"


# ── ChunkedUpload ──────────────────────────────────────────────────────────────

class ChunkedUpload(Base):
    __tablename__ = "chunked_uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    received_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus), nullable=False, default=UploadStatus.uploading
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chunks: Mapped[list["UploadChunk"]] = relationship(
        "UploadChunk", back_populates="upload", lazy="selectin"
    )


# ── UploadChunk ────────────────────────────────────────────────────────────────

class UploadChunk(Base):
    __tablename__ = "upload_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chunked_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    upload: Mapped["ChunkedUpload"] = relationship("ChunkedUpload", back_populates="chunks")


# ── ImportTask ─────────────────────────────────────────────────────────────────

class ImportTask(Base):
    __tablename__ = "import_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    upload_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("chunked_uploads.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[ImportTaskType] = mapped_column(
        Enum(ImportTaskType), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ImportTaskStatus] = mapped_column(
        Enum(ImportTaskStatus), nullable=False, default=ImportTaskStatus.pending
    )
    total_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ── TransactionalBatch ─────────────────────────────────────────────────────────

class TransactionalBatch(Base):
    __tablename__ = "transactional_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus), nullable=False, default=BatchStatus.open
    )
    operations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    committed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
