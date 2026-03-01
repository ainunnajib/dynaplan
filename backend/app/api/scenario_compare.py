"""REST API endpoints for F024: Scenario comparison."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.scenario_compare import (
    ComparisonMatrix,
    ComparisonRequest,
    ComparisonResponse,
    MatrixRequest,
    VarianceSummary,
    VarianceSummaryRequest,
)
from app.services.scenario_compare import (
    compare_versions,
    get_comparison_matrix,
    get_variance_summary,
)

router = APIRouter(tags=["scenario-compare"])


@router.post(
    "/models/{model_id}/compare",
    response_model=ComparisonResponse,
    status_code=status.HTTP_200_OK,
)
async def compare_versions_endpoint(
    model_id: uuid.UUID,
    data: ComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare multiple versions side by side for all (or selected) line items in the model.

    Returns a list of comparison rows, each containing:
    - line_item_id and line_item_name
    - dimension_key (base key without version segment)
    - values per version (dict of version_id -> float or null)
    - absolute_diff and percentage_diff (only populated when exactly 2 versions provided)
    """
    if not data.version_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one version_id must be provided",
        )

    try:
        version_uuids = [uuid.UUID(vid) for vid in data.version_ids]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID in version_ids",
        )

    line_item_uuids: List[uuid.UUID] = []
    if data.line_item_ids:
        try:
            line_item_uuids = [uuid.UUID(lid) for lid in data.line_item_ids]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid UUID in line_item_ids",
            )

    result = await compare_versions(
        db,
        model_id=model_id,
        version_ids=version_uuids,
        line_item_ids=line_item_uuids if line_item_uuids else None,
        dimension_filters=data.dimension_filters,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model or one or more versions not found",
        )

    return result


@router.post(
    "/models/{model_id}/compare/variance",
    response_model=VarianceSummary,
    status_code=status.HTTP_200_OK,
)
async def variance_summary_endpoint(
    model_id: uuid.UUID,
    data: VarianceSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregate variance statistics between exactly two versions.

    Returns:
    - total_absolute_diff: sum of absolute differences across all cells
    - avg_percentage_diff: average percentage difference (null when base is always zero)
    - changed_cells: count of cells where values differ
    - unchanged_cells: count of cells where values are identical
    - total_cells: total cells in the union of both versions
    """
    try:
        base_id = uuid.UUID(data.base_version_id)
        compare_id = uuid.UUID(data.compare_version_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID in base_version_id or compare_version_id",
        )

    line_item_uuids: List[uuid.UUID] = []
    if data.line_item_ids:
        try:
            line_item_uuids = [uuid.UUID(lid) for lid in data.line_item_ids]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid UUID in line_item_ids",
            )

    result = await get_variance_summary(
        db,
        model_id=model_id,
        base_version_id=base_id,
        compare_version_id=compare_id,
        line_item_ids=line_item_uuids if line_item_uuids else None,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model or one or more versions not found",
        )

    return result


@router.post(
    "/models/{model_id}/compare/matrix",
    response_model=ComparisonMatrix,
    status_code=status.HTTP_200_OK,
)
async def comparison_matrix_endpoint(
    model_id: uuid.UUID,
    data: MatrixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a comparison matrix for a single line item across multiple versions.

    Returns a matrix structure:
    - dimension_keys: sorted list of all dimension intersection keys
    - matrix: dict of {dimension_key -> {version_id -> value}}
    - version_names: dict of {version_id -> version name}

    Useful for building heatmap-style visualizations.
    """
    if not data.version_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one version_id must be provided",
        )

    try:
        version_uuids = [uuid.UUID(vid) for vid in data.version_ids]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID in version_ids",
        )

    try:
        line_item_uuid = uuid.UUID(data.line_item_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID for line_item_id",
        )

    result = await get_comparison_matrix(
        db,
        model_id=model_id,
        version_ids=version_uuids,
        line_item_id=line_item_uuid,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model or one or more versions not found",
        )

    return result
