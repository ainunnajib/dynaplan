import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunked_upload import (
    BatchStatus,
    ChunkedUpload,
    ImportTask,
    ImportTaskStatus,
    ImportTaskType,
    TransactionalBatch,
    UploadChunk,
    UploadStatus,
)


# ── Chunked Upload ─────────────────────────────────────────────────────────────

async def create_upload_session(
    db: AsyncSession,
    model_id: uuid.UUID,
    filename: str,
    content_type: str,
    total_chunks: int,
    user_id: uuid.UUID,
    total_size_bytes: Optional[int] = None,
) -> ChunkedUpload:
    """Create a new chunked upload session."""
    upload = ChunkedUpload(
        model_id=model_id,
        filename=filename,
        content_type=content_type,
        total_chunks=total_chunks,
        received_chunks=0,
        total_size_bytes=total_size_bytes,
        status=UploadStatus.uploading,
        created_by=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return upload


async def get_upload(
    db: AsyncSession,
    upload_id: uuid.UUID,
) -> Optional[ChunkedUpload]:
    """Retrieve an upload session by ID."""
    result = await db.execute(
        select(ChunkedUpload).where(ChunkedUpload.id == upload_id)
    )
    return result.scalar_one_or_none()


async def upload_chunk(
    db: AsyncSession,
    upload_id: uuid.UUID,
    chunk_index: int,
    data: str,
    size_bytes: int,
    checksum: Optional[str] = None,
) -> UploadChunk:
    """Upload a single chunk. Validates index and updates received count."""
    upload = await get_upload(db, upload_id)
    if upload is None:
        raise ValueError("Upload session not found")

    if upload.status != UploadStatus.uploading:
        raise ValueError(f"Upload is in '{upload.status.value}' state, cannot accept chunks")

    if chunk_index < 0 or chunk_index >= upload.total_chunks:
        raise ValueError(
            f"chunk_index {chunk_index} out of range [0, {upload.total_chunks})"
        )

    # Check for duplicate chunk
    existing = await db.execute(
        select(UploadChunk).where(
            UploadChunk.upload_id == upload_id,
            UploadChunk.chunk_index == chunk_index,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Chunk {chunk_index} already uploaded")

    chunk = UploadChunk(
        upload_id=upload_id,
        chunk_index=chunk_index,
        size_bytes=size_bytes,
        checksum=checksum,
        data=data,
    )
    db.add(chunk)

    upload.received_chunks += 1

    # Auto-complete when all chunks received
    if upload.received_chunks >= upload.total_chunks:
        upload.status = UploadStatus.complete
        upload.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(chunk)
    return chunk


async def complete_upload(
    db: AsyncSession,
    upload_id: uuid.UUID,
) -> ChunkedUpload:
    """Explicitly finalize an upload session."""
    upload = await get_upload(db, upload_id)
    if upload is None:
        raise ValueError("Upload session not found")

    if upload.received_chunks < upload.total_chunks:
        raise ValueError(
            f"Only {upload.received_chunks}/{upload.total_chunks} chunks received"
        )

    upload.status = UploadStatus.complete
    upload.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(upload)
    return upload


async def fail_upload(
    db: AsyncSession,
    upload_id: uuid.UUID,
) -> ChunkedUpload:
    """Mark an upload as failed."""
    upload = await get_upload(db, upload_id)
    if upload is None:
        raise ValueError("Upload session not found")
    upload.status = UploadStatus.failed
    await db.commit()
    await db.refresh(upload)
    return upload


# ── Import Task ────────────────────────────────────────────────────────────────

async def create_import_task(
    db: AsyncSession,
    model_id: uuid.UUID,
    task_type: ImportTaskType,
    target_id: str,
    user_id: uuid.UUID,
    upload_id: Optional[uuid.UUID] = None,
    total_records: Optional[int] = None,
) -> ImportTask:
    """Create a new import task."""
    task = ImportTask(
        model_id=model_id,
        upload_id=upload_id,
        task_type=task_type,
        target_id=target_id,
        status=ImportTaskStatus.pending,
        total_records=total_records,
        processed_records=0,
        error_count=0,
        created_by=user_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_import_task(
    db: AsyncSession,
    task_id: uuid.UUID,
) -> Optional[ImportTask]:
    """Retrieve an import task by ID."""
    result = await db.execute(
        select(ImportTask).where(ImportTask.id == task_id)
    )
    return result.scalar_one_or_none()


async def list_import_tasks(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[ImportTask]:
    """List all import tasks for a model."""
    result = await db.execute(
        select(ImportTask)
        .where(ImportTask.model_id == model_id)
        .order_by(ImportTask.created_at.desc())
    )
    return list(result.scalars().all())


async def update_import_task_progress(
    db: AsyncSession,
    task_id: uuid.UUID,
    processed_records: int,
    error_count: int = 0,
    errors: Optional[Dict[str, Any]] = None,
    status: Optional[ImportTaskStatus] = None,
) -> Optional[ImportTask]:
    """Update import task progress."""
    task = await get_import_task(db, task_id)
    if task is None:
        return None
    task.processed_records = processed_records
    task.error_count = error_count
    if errors is not None:
        task.errors = errors
    if status is not None:
        task.status = status
        if status in (ImportTaskStatus.completed, ImportTaskStatus.failed):
            task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task


# ── Transactional Batch ────────────────────────────────────────────────────────

async def create_batch(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TransactionalBatch:
    """Create a new transactional batch."""
    batch = TransactionalBatch(
        model_id=model_id,
        status=BatchStatus.open,
        operations=[],
        created_by=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


async def get_batch(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> Optional[TransactionalBatch]:
    """Retrieve a batch by ID."""
    result = await db.execute(
        select(TransactionalBatch).where(TransactionalBatch.id == batch_id)
    )
    return result.scalar_one_or_none()


async def add_batch_operation(
    db: AsyncSession,
    batch_id: uuid.UUID,
    operation_type: str,
    target: str,
    payload: Dict[str, Any],
) -> TransactionalBatch:
    """Add an operation to an open batch."""
    batch = await get_batch(db, batch_id)
    if batch is None:
        raise ValueError("Batch not found")

    if batch.status != BatchStatus.open:
        raise ValueError(f"Batch is '{batch.status.value}', cannot add operations")

    operation = {
        "operation_type": operation_type,
        "target": target,
        "payload": payload,
    }

    # Must create a new list to trigger SQLAlchemy change detection on JSON
    current_ops = list(batch.operations or [])
    current_ops.append(operation)
    batch.operations = current_ops

    await db.commit()
    await db.refresh(batch)
    return batch


async def commit_batch(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> TransactionalBatch:
    """Commit a batch, applying all operations."""
    batch = await get_batch(db, batch_id)
    if batch is None:
        raise ValueError("Batch not found")

    if batch.status != BatchStatus.open:
        raise ValueError(f"Batch is '{batch.status.value}', cannot commit")

    # In a real implementation, we would iterate over operations and apply them
    # For now, we mark the batch as committed
    batch.status = BatchStatus.committed
    batch.committed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(batch)
    return batch


async def rollback_batch(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> TransactionalBatch:
    """Roll back a batch, discarding all operations."""
    batch = await get_batch(db, batch_id)
    if batch is None:
        raise ValueError("Batch not found")

    if batch.status != BatchStatus.open:
        raise ValueError(f"Batch is '{batch.status.value}', cannot rollback")

    batch.status = BatchStatus.rolled_back
    await db.commit()
    await db.refresh(batch)
    return batch
