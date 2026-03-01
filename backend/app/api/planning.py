"""
REST API endpoints for F025: Top-down & bottom-up planning.
All endpoints require JWT authentication.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.planning import (
    AggregateRequest,
    AggregateResponse,
    BulkSpreadRequest,
    BulkSpreadResponse,
    HierarchyValuesResponse,
    RecalculateHierarchyRequest,
    RecalculateHierarchyResponse,
    SpreadRequest,
    SpreadResponse,
)
from app.services.planning import (
    aggregate_bottom_up,
    get_hierarchy_values,
    recalculate_hierarchy,
    spread_top_down,
)

router = APIRouter(prefix="/planning", tags=["planning"])


@router.post(
    "/spread",
    response_model=SpreadResponse,
    status_code=status.HTTP_200_OK,
)
async def spread_endpoint(
    data: SpreadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Spread a target value top-down from a parent dimension member to its children."""
    try:
        return await spread_top_down(
            db=db,
            line_item_id=data.line_item_id,
            parent_dimension_member_id=data.parent_member_id,
            target_value=data.target_value,
            method=data.method,
            weights=data.weights,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/aggregate",
    response_model=AggregateResponse,
    status_code=status.HTTP_200_OK,
)
async def aggregate_endpoint(
    data: AggregateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate child cell values bottom-up and write the result to the parent cell."""
    try:
        return await aggregate_bottom_up(
            db=db,
            line_item_id=data.line_item_id,
            parent_dimension_member_id=data.parent_member_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/hierarchy-values",
    response_model=HierarchyValuesResponse,
    status_code=status.HTTP_200_OK,
)
async def hierarchy_values_endpoint(
    line_item_id: uuid.UUID = Query(...),
    dimension_id: uuid.UUID = Query(...),
    parent_member_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get parent + all children values for a line item within a dimension hierarchy."""
    try:
        return await get_hierarchy_values(
            db=db,
            line_item_id=line_item_id,
            dimension_id=dimension_id,
            parent_member_id=parent_member_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/bulk-spread",
    response_model=BulkSpreadResponse,
    status_code=status.HTTP_200_OK,
)
async def bulk_spread_endpoint(
    data: BulkSpreadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply multiple spread operations in a single request."""
    try:
        results = []
        for s in data.spreads:
            result = await spread_top_down(
                db=db,
                line_item_id=s.line_item_id,
                parent_dimension_member_id=s.parent_member_id,
                target_value=s.target_value,
                method=s.method,
                weights=s.weights,
            )
            results.append(result)
        return BulkSpreadResponse(results=results)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post(
    "/recalculate-hierarchy",
    response_model=RecalculateHierarchyResponse,
    status_code=status.HTTP_200_OK,
)
async def recalculate_hierarchy_endpoint(
    data: RecalculateHierarchyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recalculate all parent values in a hierarchy via bottom-up aggregation."""
    try:
        return await recalculate_hierarchy(
            db=db,
            line_item_id=data.line_item_id,
            dimension_id=data.dimension_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
