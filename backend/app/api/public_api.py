import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.api_key import ApiKey
from app.schemas.cell import CellBulkWrite, CellQuery, CellRead, CellWrite
from app.schemas.dimension import DimensionResponse
from app.schemas.planning_model import PlanningModelResponse
from app.services.api_key import check_scope, validate_api_key
from app.services.cell import read_cells_for_line_item, write_cell, write_cells_bulk
from app.services.dimension import list_dimensions_for_model
from app.services.planning_model import get_model_by_id, list_models_for_workspace

router = APIRouter(prefix="/api/v1", tags=["public-api"])


# ── Auth dependency ─────────────────────────────────────────────────────────────

async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Validate the X-API-Key header and return the associated ApiKey record."""
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    api_key = await validate_api_key(db, raw_key=x_api_key)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    return api_key


def require_scope(required_scope: str):
    """Return a FastAPI dependency that enforces a specific scope on the API key."""
    async def _check(api_key: ApiKey = Depends(get_api_key)) -> ApiKey:
        if not check_scope(api_key, required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: '{required_scope}'",
            )
        return api_key
    return _check


# ── Models ──────────────────────────────────────────────────────────────────────

@router.get(
    "/models",
    response_model=List[PlanningModelResponse],
    summary="List all models (API key: read:models)",
)
async def public_list_models(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    """List all models in a workspace using an API key with read:models scope."""
    models = await list_models_for_workspace(db, workspace_id=workspace_id)
    return models


@router.get(
    "/models/{model_id}",
    response_model=PlanningModelResponse,
    summary="Get a model (API key: read:models)",
)
async def public_get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    """Get a single model by ID using an API key with read:models scope."""
    model = await get_model_by_id(db, model_id=model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    return model


# ── Dimensions ──────────────────────────────────────────────────────────────────

@router.get(
    "/models/{model_id}/dimensions",
    response_model=List[DimensionResponse],
    summary="List dimensions for a model (API key: read:dimensions)",
)
async def public_list_dimensions(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:dimensions")),
):
    """List all dimensions for a model using an API key with read:dimensions scope."""
    model = await get_model_by_id(db, model_id=model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    dimensions = await list_dimensions_for_model(db, model_id=model_id)
    return dimensions


# ── Cells ───────────────────────────────────────────────────────────────────────

@router.post(
    "/cells/query",
    response_model=List[CellRead],
    summary="Query cells (API key: read:cells)",
)
async def public_query_cells(
    data: CellQuery,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:cells")),
):
    """Query cells for a line item using an API key with read:cells scope."""
    return await read_cells_for_line_item(
        db,
        line_item_id=data.line_item_id,
        version_id=data.version_id,
        dimension_filters=data.dimension_filters,
    )


@router.post(
    "/cells",
    response_model=CellRead,
    status_code=status.HTTP_200_OK,
    summary="Write a single cell (API key: write:cells)",
)
async def public_write_cell(
    data: CellWrite,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:cells")),
):
    """Write (upsert) a single cell value using an API key with write:cells scope."""
    return await write_cell(
        db,
        line_item_id=data.line_item_id,
        dimension_members=data.dimension_members,
        version_id=data.version_id,
        value=data.value,
    )


@router.post(
    "/cells/bulk",
    response_model=List[CellRead],
    status_code=status.HTTP_200_OK,
    summary="Bulk write cells (API key: write:cells)",
)
async def public_write_cells_bulk(
    data: CellBulkWrite,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:cells")),
):
    """Bulk write (upsert) multiple cell values using an API key with write:cells scope."""
    return await write_cells_bulk(db, cells=data.cells)
