import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.snapshot import (
    RestoreResult,
    SnapshotCompareRequest,
    SnapshotComparison,
    SnapshotCreate,
    SnapshotDetailResponse,
    SnapshotMetadataResponse,
)
from app.services.snapshot import (
    compare_snapshots,
    create_snapshot,
    delete_snapshot,
    get_snapshot,
    list_snapshots,
    restore_snapshot,
)

router = APIRouter(tags=["snapshots"])


# ── Helpers ─────────────────────────────────────────────────────────────────────

async def _get_snapshot_or_404(
    snapshot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshot = await get_snapshot(db, snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )
    return snapshot


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/snapshots",
    response_model=SnapshotMetadataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_snapshot_endpoint(
    model_id: uuid.UUID,
    data: SnapshotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a named snapshot of the entire model state."""
    snapshot = await create_snapshot(
        db,
        model_id=model_id,
        name=data.name,
        description=data.description,
        user_id=current_user.id,
    )
    return snapshot


@router.get(
    "/models/{model_id}/snapshots",
    response_model=List[SnapshotMetadataResponse],
)
async def list_snapshots_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all snapshots for a model (metadata only, no data blob)."""
    return await list_snapshots(db, model_id=model_id)


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=SnapshotDetailResponse,
)
async def get_snapshot_endpoint(
    snapshot=Depends(_get_snapshot_or_404),
):
    """Get full snapshot detail including serialized model data."""
    return snapshot


@router.delete(
    "/snapshots/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_snapshot_endpoint(
    snapshot=Depends(_get_snapshot_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Delete a snapshot."""
    await delete_snapshot(db, snapshot)


@router.post(
    "/snapshots/{snapshot_id}/restore",
    response_model=RestoreResult,
)
async def restore_snapshot_endpoint(
    snapshot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a model to the state captured in this snapshot."""
    result = await restore_snapshot(db, snapshot_id=snapshot_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )
    return result


@router.post(
    "/snapshots/compare",
    response_model=SnapshotComparison,
)
async def compare_snapshots_endpoint(
    data: SnapshotCompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare two snapshots and return diff counts by entity type."""
    result = await compare_snapshots(
        db,
        snapshot_id_a=data.snapshot_a_id,
        snapshot_id_b=data.snapshot_b_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both snapshots not found",
        )
    return result
