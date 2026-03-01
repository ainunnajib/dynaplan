import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.bulk_job import BulkJobStatus, BulkJobType
from app.models.planning_model import PlanningModel
from app.schemas.bulk_ops import (
    BulkCopyRequest,
    BulkDeleteRequest,
    BulkJobProgress,
    BulkJobResponse,
    BulkReadRequest,
    BulkReadResponse,
    BulkCellRead,
    BulkWriteRequest,
)
from app.services.bulk_ops import (
    bulk_copy_cells,
    bulk_delete_cells,
    bulk_read_cells,
    bulk_write_cells,
    cancel_bulk_job,
    create_bulk_job,
    get_bulk_job,
    list_bulk_jobs,
)
from sqlalchemy import select

router = APIRouter(tags=["bulk_ops"])


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _job_or_404(job):
    if job is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Bulk job not found",
        )
    return job


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


def _job_to_progress(job) -> BulkJobProgress:
    percentage = None
    if job.total_rows and job.total_rows > 0:
        percentage = round((job.processed_rows / job.total_rows) * 100, 2)
    return BulkJobProgress(
        job_id=job.id,
        status=job.status,
        processed_rows=job.processed_rows,
        total_rows=job.total_rows,
        failed_rows=job.failed_rows,
        percentage=percentage,
    )


def _cell_read_to_schema(cell_read) -> BulkCellRead:
    return BulkCellRead(
        line_item_id=cell_read.line_item_id,
        dimension_key=cell_read.dimension_key,
        dimension_members=cell_read.dimension_members,
        value=cell_read.value,
        value_type=cell_read.value_type,
    )


# ── Bulk write ──────────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/bulk/write",
    response_model=BulkJobResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def bulk_write_endpoint(
    model_id: uuid.UUID,
    data: BulkWriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Bulk write cells for a model. Returns a job that tracks progress."""
    await _get_model_or_404(db, model_id)

    chunk_size = data.chunk_size or 100
    total_rows = len(data.cells)

    job = await create_bulk_job(
        db=db,
        model_id=model_id,
        job_type=BulkJobType.import_cells,
        config={"chunk_size": chunk_size, "total_cells": total_rows},
        user_id=current_user.id,
        total_rows=total_rows,
    )

    # Convert cell inputs to dicts for the service
    cells_dicts = [
        {
            "line_item_id": str(c.line_item_id),
            "dimension_members": [str(m) for m in c.dimension_members],
            "value": c.value,
        }
        for c in data.cells
    ]

    await bulk_write_cells(
        db=db,
        model_id=model_id,
        cells=cells_dicts,
        job_id=job.id,
        chunk_size=chunk_size,
    )

    # Refresh job after write
    updated_job = await get_bulk_job(db, job.id)
    return updated_job


# ── Bulk read ───────────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/bulk/read",
    response_model=BulkReadResponse,
)
async def bulk_read_endpoint(
    model_id: uuid.UUID,
    data: BulkReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Bulk read cells with pagination and optional filters."""
    await _get_model_or_404(db, model_id)

    result = await bulk_read_cells(
        db=db,
        model_id=model_id,
        line_item_ids=data.line_item_ids,
        dimension_filters=data.dimension_filters,
        limit=data.limit,
        offset=data.offset,
    )

    cells_out = [_cell_read_to_schema(c) for c in result["cells"]]

    return BulkReadResponse(
        cells=cells_out,
        total_count=result["total_count"],
        has_more=result["has_more"],
    )


# ── Bulk delete ─────────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/bulk/delete",
    response_model=BulkJobResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def bulk_delete_endpoint(
    model_id: uuid.UUID,
    data: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Bulk delete cells matching the given criteria. Returns a job."""
    await _get_model_or_404(db, model_id)

    job = await create_bulk_job(
        db=db,
        model_id=model_id,
        job_type=BulkJobType.delete_cells,
        config={
            "line_item_id": str(data.line_item_id) if data.line_item_id else None,
            "dimension_key_prefix": data.dimension_key_prefix,
        },
        user_id=current_user.id,
    )

    await bulk_delete_cells(
        db=db,
        model_id=model_id,
        line_item_id=data.line_item_id,
        dimension_key_prefix=data.dimension_key_prefix,
        job_id=job.id,
    )

    updated_job = await get_bulk_job(db, job.id)
    return updated_job


# ── Bulk copy ───────────────────────────────────────────────────────────────────

@router.post(
    "/bulk/copy",
    response_model=BulkJobResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def bulk_copy_endpoint(
    data: BulkCopyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Copy cells between models using a line item ID mapping. Returns a job."""
    await _get_model_or_404(db, data.source_model_id)
    await _get_model_or_404(db, data.target_model_id)

    job = await create_bulk_job(
        db=db,
        model_id=data.source_model_id,
        job_type=BulkJobType.copy_cells,
        config={
            "source_model_id": str(data.source_model_id),
            "target_model_id": str(data.target_model_id),
            "line_item_mapping": data.line_item_mapping,
        },
        user_id=current_user.id,
    )

    await bulk_copy_cells(
        db=db,
        source_model_id=data.source_model_id,
        target_model_id=data.target_model_id,
        line_item_mapping=data.line_item_mapping,
        job_id=job.id,
    )

    updated_job = await get_bulk_job(db, job.id)
    return updated_job


# ── Job status ──────────────────────────────────────────────────────────────────

@router.get(
    "/bulk/jobs/{job_id}",
    response_model=BulkJobProgress,
)
async def get_job_status_endpoint(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the status and progress of a bulk job."""
    job = await get_bulk_job(db, job_id)
    _job_or_404(job)
    return _job_to_progress(job)


# ── List jobs for model ─────────────────────────────────────────────────────────

@router.get(
    "/models/{model_id}/bulk/jobs",
    response_model=List[BulkJobResponse],
)
async def list_jobs_endpoint(
    model_id: uuid.UUID,
    status: Optional[BulkJobStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List bulk jobs for a model, optionally filtered by status."""
    await _get_model_or_404(db, model_id)
    jobs = await list_bulk_jobs(db, model_id, status)
    return jobs


# ── Cancel job ──────────────────────────────────────────────────────────────────

@router.post(
    "/bulk/jobs/{job_id}/cancel",
    response_model=BulkJobResponse,
)
async def cancel_job_endpoint(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cancel a pending or running bulk job."""
    job = await get_bulk_job(db, job_id)
    _job_or_404(job)

    if job.status not in (BulkJobStatus.pending, BulkJobStatus.running):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a job with status '{job.status.value}'",
        )

    cancelled = await cancel_bulk_job(db, job_id)
    return cancelled
