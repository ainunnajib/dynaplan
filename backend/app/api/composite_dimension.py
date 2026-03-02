import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.composite_dimension import CompositeDimension, CompositeDimensionMember
from app.models.user import User
from app.schemas.composite_dimension import (
    CompositeDimensionCreate,
    CompositeDimensionResponse,
    CompositeIntersectionCreate,
    CompositeIntersectionResponse,
)
from app.services.composite_dimension import (
    CompositeDimensionValidationError,
    create_composite_dimension,
    delete_composite_dimension,
    ensure_composite_intersection_member,
    get_composite_dimension_by_id,
    list_composite_dimensions_for_model,
    list_composite_intersection_members,
    parse_source_member_key,
)
from app.services.workspace_quota import WorkspaceQuotaExceededError

router = APIRouter(tags=["composite-dimensions"])


def _serialize_composite_dimension(
    composite_dimension: CompositeDimension,
) -> CompositeDimensionResponse:
    dimension = composite_dimension.dimension
    if dimension is None:
        raise CompositeDimensionValidationError("Composite dimension is missing base dimension")
    return CompositeDimensionResponse(
        id=composite_dimension.id,
        dimension_id=composite_dimension.dimension_id,
        model_id=composite_dimension.model_id,
        name=dimension.name,
        dimension_type=dimension.dimension_type,
        source_dimension_ids=[
            source.source_dimension_id
            for source in sorted(
                composite_dimension.source_dimensions,
                key=lambda source: source.sort_order,
            )
        ],
        created_at=composite_dimension.created_at,
        updated_at=composite_dimension.updated_at,
    )


def _serialize_composite_member(
    member: CompositeDimensionMember,
) -> CompositeIntersectionResponse:
    if member.dimension_item is None:
        raise CompositeDimensionValidationError("Composite intersection is missing dimension item")
    return CompositeIntersectionResponse(
        id=member.id,
        dimension_item_id=member.dimension_item_id,
        composite_dimension_id=member.composite_dimension_id,
        source_member_ids=parse_source_member_key(member.source_member_key),
        name=member.dimension_item.name,
        code=member.dimension_item.code,
        sort_order=member.dimension_item.sort_order,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


async def _get_composite_dimension_or_404(
    composite_dimension_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompositeDimension:
    composite_dimension = await get_composite_dimension_by_id(db, composite_dimension_id)
    if composite_dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Composite dimension not found",
        )
    return composite_dimension


@router.post(
    "/models/{model_id}/composite-dimensions",
    response_model=CompositeDimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_composite_dimension_endpoint(
    model_id: uuid.UUID,
    data: CompositeDimensionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        created = await create_composite_dimension(db, model_id=model_id, data=data)
        return _serialize_composite_dimension(created)
    except WorkspaceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except CompositeDimensionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/models/{model_id}/composite-dimensions",
    response_model=List[CompositeDimensionResponse],
)
async def list_composite_dimensions_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await list_composite_dimensions_for_model(db, model_id=model_id)
    return [_serialize_composite_dimension(row) for row in rows]


@router.get(
    "/composite-dimensions/{composite_dimension_id}",
    response_model=CompositeDimensionResponse,
)
async def get_composite_dimension_endpoint(
    composite_dimension=Depends(_get_composite_dimension_or_404),
):
    return _serialize_composite_dimension(composite_dimension)


@router.delete(
    "/composite-dimensions/{composite_dimension_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_composite_dimension_endpoint(
    composite_dimension=Depends(_get_composite_dimension_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_composite_dimension(db, composite_dimension)


@router.post(
    "/composite-dimensions/{composite_dimension_id}/intersections",
    response_model=CompositeIntersectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_composite_intersection_endpoint(
    composite_dimension_id: uuid.UUID,
    data: CompositeIntersectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    composite_dimension = await get_composite_dimension_by_id(db, composite_dimension_id)
    if composite_dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Composite dimension not found",
        )
    try:
        intersection = await ensure_composite_intersection_member(
            db,
            composite_dimension=composite_dimension,
            source_member_ids=data.source_member_ids,
        )
        await db.commit()
        intersections = await list_composite_intersection_members(
            db, composite_dimension_id=composite_dimension_id
        )
        refreshed = next(
            (member for member in intersections if member.id == intersection.id),
            None,
        )
        if refreshed is None:
            raise CompositeDimensionValidationError("Failed to create composite intersection")
        return _serialize_composite_member(refreshed)
    except CompositeDimensionValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/composite-dimensions/{composite_dimension_id}/intersections",
    response_model=List[CompositeIntersectionResponse],
)
async def list_composite_intersections_endpoint(
    composite_dimension=Depends(_get_composite_dimension_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    intersections = await list_composite_intersection_members(
        db,
        composite_dimension_id=composite_dimension.id,
    )
    return [_serialize_composite_member(intersection) for intersection in intersections]
