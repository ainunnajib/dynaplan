import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.subset import (
    AddLineItemMembersRequest,
    AddMembersRequest,
    LineItemSubsetCreate,
    LineItemSubsetMemberResponse,
    LineItemSubsetResponse,
    LineItemSubsetSummaryResponse,
    LineItemSubsetUpdate,
    ListSubsetCreate,
    ListSubsetMemberResponse,
    ListSubsetResponse,
    ListSubsetSummaryResponse,
    ListSubsetUpdate,
    ResolvedLineItemMember,
    ResolvedLineItemMembersResponse,
    ResolvedMemberItem,
    ResolvedMembersResponse,
)
from app.services.dimension import get_dimension_by_id, get_dimension_item_by_id
from app.services.module import get_line_item_by_id, get_module_by_id
from app.services.subset import (
    add_line_item_subset_members,
    add_list_subset_members,
    create_line_item_subset,
    create_list_subset,
    delete_line_item_subset,
    delete_list_subset,
    get_line_item_subset_by_id,
    get_line_item_subset_member_by_id,
    get_list_subset_by_id,
    get_list_subset_member_by_id,
    list_line_item_subsets_for_module,
    list_subsets_for_dimension,
    remove_line_item_subset_member,
    remove_list_subset_member,
    resolve_line_item_subset_members,
    resolve_list_subset_members,
    update_line_item_subset,
    update_list_subset,
)

router = APIRouter(tags=["subsets"])


# ══════════════════════════════════════════════════════════════════════════════
# List Subsets
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/dimensions/{dimension_id}/subsets",
    response_model=ListSubsetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_list_subset_endpoint(
    dimension_id: uuid.UUID,
    data: ListSubsetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dimension = await get_dimension_by_id(db, dimension_id)
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )
    return await create_list_subset(db, dimension_id=dimension_id, data=data)


@router.get(
    "/dimensions/{dimension_id}/subsets",
    response_model=List[ListSubsetSummaryResponse],
)
async def list_subsets_endpoint(
    dimension_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dimension = await get_dimension_by_id(db, dimension_id)
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )
    return await list_subsets_for_dimension(db, dimension_id=dimension_id)


@router.get(
    "/subsets/{subset_id}",
    response_model=ListSubsetResponse,
)
async def get_subset_endpoint(
    subset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_list_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subset not found",
        )
    return subset


@router.put(
    "/subsets/{subset_id}",
    response_model=ListSubsetResponse,
)
async def update_subset_endpoint(
    subset_id: uuid.UUID,
    data: ListSubsetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_list_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subset not found",
        )
    return await update_list_subset(db, subset, data)


@router.delete(
    "/subsets/{subset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subset_endpoint(
    subset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_list_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subset not found",
        )
    await delete_list_subset(db, subset)


@router.post(
    "/subsets/{subset_id}/members",
    response_model=List[ListSubsetMemberResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_members_endpoint(
    subset_id: uuid.UUID,
    data: AddMembersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_list_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subset not found",
        )
    # Validate all dimension item IDs belong to the subset's dimension
    for item_id in data.dimension_item_ids:
        item = await get_dimension_item_by_id(db, item_id)
        if item is None or item.dimension_id != subset.dimension_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dimension item {item_id} not found in this dimension",
            )
    return await add_list_subset_members(db, subset_id, data.dimension_item_ids)


@router.delete(
    "/subsets/{subset_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member_endpoint(
    subset_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_list_subset_member_by_id(db, member_id)
    if member is None or member.subset_id != subset_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    await remove_list_subset_member(db, member)


@router.get(
    "/subsets/{subset_id}/resolved",
    response_model=ResolvedMembersResponse,
)
async def get_resolved_members_endpoint(
    subset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_list_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subset not found",
        )
    items = await resolve_list_subset_members(db, subset)
    return ResolvedMembersResponse(
        subset_id=subset.id,
        subset_name=subset.name,
        is_dynamic=subset.is_dynamic,
        members=[
            ResolvedMemberItem(id=item.id, name=item.name, code=item.code)
            for item in items
        ],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Line Item Subsets
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/modules/{module_id}/line-item-subsets",
    response_model=LineItemSubsetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_line_item_subset_endpoint(
    module_id: uuid.UUID,
    data: LineItemSubsetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await get_module_by_id(db, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return await create_line_item_subset(db, module_id=module_id, data=data)


@router.get(
    "/modules/{module_id}/line-item-subsets",
    response_model=List[LineItemSubsetSummaryResponse],
)
async def list_line_item_subsets_endpoint(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await get_module_by_id(db, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return await list_line_item_subsets_for_module(db, module_id=module_id)


@router.get(
    "/line-item-subsets/{subset_id}",
    response_model=LineItemSubsetResponse,
)
async def get_line_item_subset_endpoint(
    subset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_line_item_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item subset not found",
        )
    return subset


@router.put(
    "/line-item-subsets/{subset_id}",
    response_model=LineItemSubsetResponse,
)
async def update_line_item_subset_endpoint(
    subset_id: uuid.UUID,
    data: LineItemSubsetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_line_item_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item subset not found",
        )
    return await update_line_item_subset(db, subset, data)


@router.delete(
    "/line-item-subsets/{subset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_line_item_subset_endpoint(
    subset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_line_item_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item subset not found",
        )
    await delete_line_item_subset(db, subset)


@router.post(
    "/line-item-subsets/{subset_id}/members",
    response_model=List[LineItemSubsetMemberResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_line_item_members_endpoint(
    subset_id: uuid.UUID,
    data: AddLineItemMembersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_line_item_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item subset not found",
        )
    # Validate all line item IDs belong to the subset's module
    for li_id in data.line_item_ids:
        li = await get_line_item_by_id(db, li_id)
        if li is None or li.module_id != subset.module_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line item {li_id} not found in this module",
            )
    return await add_line_item_subset_members(db, subset_id, data.line_item_ids)


@router.delete(
    "/line-item-subsets/{subset_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_line_item_member_endpoint(
    subset_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = await get_line_item_subset_member_by_id(db, member_id)
    if member is None or member.subset_id != subset_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    await remove_line_item_subset_member(db, member)


@router.get(
    "/line-item-subsets/{subset_id}/resolved",
    response_model=ResolvedLineItemMembersResponse,
)
async def get_resolved_line_item_members_endpoint(
    subset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subset = await get_line_item_subset_by_id(db, subset_id)
    if subset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line item subset not found",
        )
    items = await resolve_line_item_subset_members(db, subset)
    return ResolvedLineItemMembersResponse(
        subset_id=subset.id,
        subset_name=subset.name,
        members=[
            ResolvedLineItemMember(id=item.id, name=item.name)
            for item in items
        ],
    )
