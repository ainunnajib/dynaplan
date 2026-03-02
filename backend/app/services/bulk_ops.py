import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulk_job import BulkJob, BulkJobStatus, BulkJobType
from app.models.cell import CellValue
from app.models.module import LineItem, Module
from app.services.cell import write_cell, _cell_to_read


# ── Job management ──────────────────────────────────────────────────────────────

async def create_bulk_job(
    db: AsyncSession,
    model_id: uuid.UUID,
    job_type: BulkJobType,
    config: Optional[Dict[str, Any]],
    user_id: uuid.UUID,
    total_rows: Optional[int] = None,
) -> BulkJob:
    """Create and persist a new bulk job record."""
    job = BulkJob(
        model_id=model_id,
        job_type=job_type,
        status=BulkJobStatus.pending,
        total_rows=total_rows,
        processed_rows=0,
        failed_rows=0,
        config=config or {},
        created_by=user_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_bulk_job(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> Optional[BulkJob]:
    """Retrieve a bulk job by ID."""
    result = await db.execute(
        select(BulkJob).where(BulkJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def list_bulk_jobs(
    db: AsyncSession,
    model_id: uuid.UUID,
    status: Optional[BulkJobStatus] = None,
) -> List[BulkJob]:
    """List bulk jobs for a model, optionally filtered by status."""
    query = select(BulkJob).where(BulkJob.model_id == model_id)
    if status is not None:
        query = query.where(BulkJob.status == status)
    query = query.order_by(BulkJob.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def cancel_bulk_job(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> Optional[BulkJob]:
    """Cancel a job if it is still pending or running. Returns None if not found or not cancellable."""
    job = await get_bulk_job(db, job_id)
    if job is None:
        return None
    if job.status not in (BulkJobStatus.pending, BulkJobStatus.running):
        return job  # Already in terminal state — return as-is
    job.status = BulkJobStatus.cancelled
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


async def update_job_progress(
    db: AsyncSession,
    job_id: uuid.UUID,
    processed: int,
    failed: int = 0,
) -> None:
    """Update processed and failed row counts on a job."""
    job = await get_bulk_job(db, job_id)
    if job is None:
        return
    job.processed_rows = processed
    job.failed_rows = failed
    await db.commit()


async def complete_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    summary: Optional[Dict[str, Any]] = None,
) -> Optional[BulkJob]:
    """Mark a job as completed."""
    job = await get_bulk_job(db, job_id)
    if job is None:
        return None
    job.status = BulkJobStatus.completed
    job.completed_at = datetime.now(timezone.utc)
    if summary is not None:
        job.result_summary = summary
    await db.commit()
    await db.refresh(job)
    return job


async def fail_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
) -> Optional[BulkJob]:
    """Mark a job as failed with an error message."""
    job = await get_bulk_job(db, job_id)
    if job is None:
        return None
    job.status = BulkJobStatus.failed
    job.error_message = error_message
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


# ── Bulk cell operations ────────────────────────────────────────────────────────

async def bulk_write_cells(
    db: AsyncSession,
    model_id: uuid.UUID,
    cells: List[Dict[str, Any]],
    job_id: Optional[uuid.UUID] = None,
    chunk_size: int = 100,
) -> Dict[str, int]:
    """
    Write cells in chunks. Updates job progress after each chunk.

    Each cell dict must have: line_item_id, dimension_members, value.

    Returns a summary dict with processed and failed counts.
    """
    # Mark job as running
    if job_id is not None:
        job = await get_bulk_job(db, job_id)
        if job is not None:
            job.status = BulkJobStatus.running
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

    total_processed = 0
    total_failed = 0

    # Process in chunks
    for chunk_start in range(0, len(cells), chunk_size):
        chunk = cells[chunk_start: chunk_start + chunk_size]
        for cell_data in chunk:
            try:
                line_item_id = uuid.UUID(str(cell_data["line_item_id"]))
                dimension_members = [
                    uuid.UUID(str(m)) for m in cell_data["dimension_members"]
                ]
                version_id_raw = cell_data.get("version_id")
                version_id = (
                    uuid.UUID(str(version_id_raw))
                    if version_id_raw is not None
                    else None
                )
                value = cell_data["value"]
                await write_cell(
                    db,
                    line_item_id,
                    dimension_members,
                    version_id,
                    value,
                )
                total_processed += 1
            except Exception:
                total_failed += 1

        # Update progress after each chunk
        if job_id is not None:
            await update_job_progress(db, job_id, total_processed, total_failed)

    # Finalize job
    if job_id is not None:
        summary = {
            "processed_rows": total_processed,
            "failed_rows": total_failed,
        }
        await complete_job(db, job_id, summary)

    return {"processed_rows": total_processed, "failed_rows": total_failed}


async def bulk_read_cells(
    db: AsyncSession,
    model_id: uuid.UUID,
    line_item_ids: Optional[List[uuid.UUID]] = None,
    dimension_filters: Optional[Dict[str, List[uuid.UUID]]] = None,
    limit: int = 1000,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Read cells with pagination. Optionally filter by line item IDs and dimension members.

    Returns dict with cells list, total_count, and has_more.
    """
    # Build base query — join through modules to scope by model
    query = (
        select(CellValue)
        .join(LineItem, CellValue.line_item_id == LineItem.id)
        .join(Module, LineItem.module_id == Module.id)
        .where(Module.model_id == model_id)
    )

    if line_item_ids:
        query = query.where(CellValue.line_item_id.in_(line_item_ids))

    result = await db.execute(query)
    all_cells = list(result.scalars().all())

    # Apply dimension filters in Python (consistent with cell service)
    if dimension_filters:
        filtered = []
        for cell in all_cells:
            key_parts = set(cell.dimension_key.split("|")) if cell.dimension_key else set()
            matches = True
            for _dim_id, allowed_members in dimension_filters.items():
                allowed_strs = {str(m) for m in allowed_members}
                if not key_parts.intersection(allowed_strs):
                    matches = False
                    break
            if matches:
                filtered.append(cell)
        all_cells = filtered

    total_count = len(all_cells)
    paginated = all_cells[offset: offset + limit]
    has_more = (offset + limit) < total_count

    return {
        "cells": [_cell_to_read(c) for c in paginated],
        "total_count": total_count,
        "has_more": has_more,
    }


async def bulk_delete_cells(
    db: AsyncSession,
    model_id: uuid.UUID,
    line_item_id: Optional[uuid.UUID] = None,
    dimension_key_prefix: Optional[str] = None,
    job_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """
    Delete cells matching the given criteria.

    If line_item_id is provided, only cells for that line item are deleted.
    If dimension_key_prefix is provided, only cells whose dimension_key starts
    with that prefix are deleted.
    If neither is provided, all cells for the model are deleted.

    Returns summary dict.
    """
    if job_id is not None:
        job = await get_bulk_job(db, job_id)
        if job is not None:
            job.status = BulkJobStatus.running
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

    # Fetch matching cells first (to respect dimension_key_prefix filter)
    query = (
        select(CellValue)
        .join(LineItem, CellValue.line_item_id == LineItem.id)
        .join(Module, LineItem.module_id == Module.id)
        .where(Module.model_id == model_id)
    )
    if line_item_id is not None:
        query = query.where(CellValue.line_item_id == line_item_id)

    result = await db.execute(query)
    all_cells = list(result.scalars().all())

    if dimension_key_prefix is not None:
        all_cells = [
            c for c in all_cells
            if c.dimension_key and c.dimension_key.startswith(dimension_key_prefix)
        ]

    deleted_count = 0
    for cell in all_cells:
        await db.delete(cell)
        deleted_count += 1

    await db.commit()

    summary = {"deleted_rows": deleted_count}

    if job_id is not None:
        job = await get_bulk_job(db, job_id)
        if job is not None:
            job.processed_rows = deleted_count
            job.status = BulkJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = summary
            await db.commit()

    return summary


async def bulk_copy_cells(
    db: AsyncSession,
    source_model_id: uuid.UUID,
    target_model_id: uuid.UUID,
    line_item_mapping: Dict[str, str],
    job_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """
    Copy cells from source model to target model using a line item ID mapping.

    line_item_mapping: {source_line_item_id_str -> target_line_item_id_str}
    """
    if job_id is not None:
        job = await get_bulk_job(db, job_id)
        if job is not None:
            job.status = BulkJobStatus.running
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

    total_processed = 0
    total_failed = 0

    for source_li_str, target_li_str in line_item_mapping.items():
        try:
            source_li_id = uuid.UUID(source_li_str)
            target_li_id = uuid.UUID(target_li_str)
        except (ValueError, AttributeError):
            total_failed += 1
            continue

        # Fetch source cells
        src_result = await db.execute(
            select(CellValue).where(CellValue.line_item_id == source_li_id)
        )
        source_cells = list(src_result.scalars().all())

        for src_cell in source_cells:
            try:
                dimension_members: List[uuid.UUID] = []
                if src_cell.dimension_key:
                    for part in src_cell.dimension_key.split("|"):
                        if not part:
                            continue
                        try:
                            dimension_members.append(uuid.UUID(part))
                        except ValueError:
                            continue

                # Determine value to copy
                if src_cell.value_boolean is not None:
                    value = src_cell.value_boolean
                elif src_cell.value_number is not None:
                    value = src_cell.value_number
                elif src_cell.value_text is not None:
                    value = src_cell.value_text
                else:
                    value = None

                await write_cell(
                    db,
                    target_li_id,
                    dimension_members,
                    src_cell.version_id,
                    value,
                )
                total_processed += 1
            except Exception:
                total_failed += 1

    summary = {
        "processed_rows": total_processed,
        "failed_rows": total_failed,
    }

    if job_id is not None:
        job = await get_bulk_job(db, job_id)
        if job is not None:
            job.processed_rows = total_processed
            job.failed_rows = total_failed
            job.status = BulkJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = summary
            await db.commit()

    return summary
