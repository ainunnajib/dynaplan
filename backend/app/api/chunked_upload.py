import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.chunked_upload import BatchStatus, UploadStatus
from app.models.planning_model import PlanningModel
from app.schemas.chunked_upload import (
    BatchOperationRequest,
    ChunkedUploadCreate,
    ChunkedUploadResponse,
    ChunkResponse,
    ChunkUploadRequest,
    ImportTaskCreate,
    ImportTaskResponse,
    TransactionalBatchCreate,
    TransactionalBatchResponse,
)
from app.services.chunked_upload import (
    add_batch_operation,
    commit_batch,
    complete_upload,
    create_batch,
    create_import_task,
    create_upload_session,
    get_batch,
    get_import_task,
    get_upload,
    list_import_tasks,
    rollback_batch,
    upload_chunk,
)

router = APIRouter(tags=["chunked_upload"])


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_model_or_404(db: AsyncSession, model_id: uuid.UUID) -> PlanningModel:
    result = await db.execute(
        select(PlanningModel).where(PlanningModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    return model


# ── Chunked Upload endpoints ──────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/uploads",
    response_model=ChunkedUploadResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_upload_endpoint(
    model_id: uuid.UUID,
    data: ChunkedUploadCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new chunked upload session."""
    await _get_model_or_404(db, model_id)

    if data.total_chunks < 1:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="total_chunks must be at least 1",
        )

    upload = await create_upload_session(
        db=db,
        model_id=model_id,
        filename=data.filename,
        content_type=data.content_type,
        total_chunks=data.total_chunks,
        user_id=current_user.id,
        total_size_bytes=data.total_size_bytes,
    )
    return upload


@router.post(
    "/uploads/{upload_id}/chunks",
    response_model=ChunkResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_chunk_endpoint(
    upload_id: uuid.UUID,
    data: ChunkUploadRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload a single chunk to an upload session."""
    try:
        chunk = await upload_chunk(
            db=db,
            upload_id=upload_id,
            chunk_index=data.chunk_index,
            data=data.data,
            size_bytes=data.size_bytes,
            checksum=data.checksum,
        )
        return chunk
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/uploads/{upload_id}",
    response_model=ChunkedUploadResponse,
)
async def get_upload_endpoint(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get upload session status."""
    upload = await get_upload(db, upload_id)
    if upload is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )
    return upload


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=ChunkedUploadResponse,
)
async def complete_upload_endpoint(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Finalize an upload session."""
    try:
        upload = await complete_upload(db, upload_id)
        return upload
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ── Import Task endpoints ─────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/import-tasks",
    response_model=ImportTaskResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_import_task_endpoint(
    model_id: uuid.UUID,
    data: ImportTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new import task."""
    await _get_model_or_404(db, model_id)

    task = await create_import_task(
        db=db,
        model_id=model_id,
        task_type=data.task_type,
        target_id=data.target_id,
        user_id=current_user.id,
        upload_id=data.upload_id,
        total_records=data.total_records,
    )
    return task


@router.get(
    "/import-tasks/{task_id}",
    response_model=ImportTaskResponse,
)
async def get_import_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get import task status."""
    task = await get_import_task(db, task_id)
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Import task not found",
        )
    return task


@router.get(
    "/models/{model_id}/import-tasks",
    response_model=List[ImportTaskResponse],
)
async def list_import_tasks_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all import tasks for a model."""
    await _get_model_or_404(db, model_id)
    tasks = await list_import_tasks(db, model_id)
    return tasks


# ── Transaction endpoints ─────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/transactions",
    response_model=TransactionalBatchResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_transaction_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new transactional batch."""
    await _get_model_or_404(db, model_id)

    batch = await create_batch(
        db=db,
        model_id=model_id,
        user_id=current_user.id,
    )
    return batch


@router.post(
    "/transactions/{batch_id}/operations",
    response_model=TransactionalBatchResponse,
)
async def add_operation_endpoint(
    batch_id: uuid.UUID,
    data: BatchOperationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add an operation to an open transaction batch."""
    try:
        batch = await add_batch_operation(
            db=db,
            batch_id=batch_id,
            operation_type=data.operation_type,
            target=data.target,
            payload=data.payload,
        )
        return batch
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/transactions/{batch_id}/commit",
    response_model=TransactionalBatchResponse,
)
async def commit_transaction_endpoint(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Commit a transaction batch."""
    try:
        batch = await commit_batch(db, batch_id)
        return batch
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/transactions/{batch_id}/rollback",
    response_model=TransactionalBatchResponse,
)
async def rollback_transaction_endpoint(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Roll back a transaction batch."""
    try:
        batch = await rollback_batch(db, batch_id)
        return batch
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/transactions/{batch_id}",
    response_model=TransactionalBatchResponse,
)
async def get_transaction_endpoint(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get transaction batch status."""
    batch = await get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Transaction batch not found",
        )
    return batch
