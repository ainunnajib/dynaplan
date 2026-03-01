import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.cell import CellBulkWrite, CellQuery, CellRead, CellWrite
from app.services.cell import (
    delete_cells_for_line_item,
    read_cells_for_line_item,
    write_cell,
    write_cells_bulk,
)
from app.services.workspace_quota import WorkspaceQuotaExceededError

router = APIRouter(prefix="/cells", tags=["cells"])


@router.post(
    "",
    response_model=CellRead,
    status_code=status.HTTP_200_OK,
)
async def write_cell_endpoint(
    data: CellWrite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Write (upsert) a single cell value."""
    try:
        return await write_cell(
            db,
            line_item_id=data.line_item_id,
            dimension_members=data.dimension_members,
            value=data.value,
        )
    except WorkspaceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/bulk",
    response_model=List[CellRead],
    status_code=status.HTTP_200_OK,
)
async def write_cells_bulk_endpoint(
    data: CellBulkWrite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Write (upsert) multiple cell values at once."""
    try:
        return await write_cells_bulk(db, cells=data.cells)
    except WorkspaceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/query",
    response_model=List[CellRead],
    status_code=status.HTTP_200_OK,
)
async def query_cells_endpoint(
    data: CellQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read cells for a line item, with optional dimension filtering."""
    return await read_cells_for_line_item(
        db,
        line_item_id=data.line_item_id,
        dimension_filters=data.dimension_filters,
    )


@router.delete(
    "/line-item/{line_item_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_cells_endpoint(
    line_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all cells for a given line item."""
    deleted_count = await delete_cells_for_line_item(db, line_item_id=line_item_id)
    return {"deleted": deleted_count}
