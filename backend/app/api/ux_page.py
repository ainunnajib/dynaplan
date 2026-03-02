import uuid
from typing import List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ux_page import (
    UXCardReorderRequest,
    UXContextSelectorCreate,
    UXContextSelectorResponse,
    UXPageCardCreate,
    UXPageCardResponse,
    UXPageCardUpdate,
    UXPageCreate,
    UXPageDetailResponse,
    UXPagePublishRequest,
    UXPageReorderRequest,
    UXPageResponse,
    UXPageUpdate,
)
from app.services.ux_page import (
    create_ux_card,
    create_ux_context_selector,
    create_ux_page,
    delete_ux_card,
    delete_ux_context_selector,
    delete_ux_page,
    get_ux_card_by_id,
    get_ux_context_selector_by_id,
    get_ux_page_by_id,
    list_ux_pages_for_model,
    publish_ux_page,
    reorder_ux_cards,
    reorder_ux_pages,
    update_ux_card,
    update_ux_page,
)

router = APIRouter(tags=["ux-pages"])


# -- Dependency helpers --------------------------------------------------------

async def _get_owned_page(
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = await get_ux_page_by_id(db, page_id)
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found",
        )
    if page.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this page",
        )
    return page


async def _get_owned_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    card = await get_ux_card_by_id(db, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )
    page = await get_ux_page_by_id(db, card.page_id)
    if page is None or page.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this card",
        )
    return card


async def _get_owned_selector(
    selector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    selector = await get_ux_context_selector_by_id(db, selector_id)
    if selector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context selector not found",
        )
    page = await get_ux_page_by_id(db, selector.page_id)
    if page is None or page.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this context selector",
        )
    return selector


async def _validate_parent_page(
    db: AsyncSession,
    parent_page_id: Optional[uuid.UUID],
    model_id: uuid.UUID,
    owner_id: uuid.UUID,
    current_page_id: Optional[uuid.UUID] = None,
) -> Optional[uuid.UUID]:
    if parent_page_id is None:
        return None

    parent_page = await get_ux_page_by_id(db, parent_page_id)
    if parent_page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent page not found",
        )

    if parent_page.model_id != model_id or parent_page.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent page must belong to the same model",
        )

    if current_page_id is not None and parent_page.id == current_page_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A page cannot be its own parent",
        )

    if current_page_id is not None:
        seen: Set[uuid.UUID] = {parent_page.id}
        ancestor = parent_page
        while ancestor.parent_page_id is not None:
            if ancestor.parent_page_id == current_page_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent relationship would create a cycle",
                )
            if ancestor.parent_page_id in seen:
                break
            seen.add(ancestor.parent_page_id)
            next_parent = await get_ux_page_by_id(db, ancestor.parent_page_id)
            if next_parent is None:
                break
            ancestor = next_parent

    return parent_page_id


# -- Page routes ---------------------------------------------------------------

@router.post(
    "/models/{model_id}/pages",
    response_model=UXPageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_page_route(
    model_id: uuid.UUID,
    data: UXPageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parent_page_id = await _validate_parent_page(
        db,
        data.parent_page_id,
        model_id=model_id,
        owner_id=current_user.id,
    )
    page_data = data.model_copy(update={"parent_page_id": parent_page_id})
    page = await create_ux_page(
        db,
        page_data,
        model_id=model_id,
        owner_id=current_user.id,
    )
    return page


@router.get(
    "/models/{model_id}/pages",
    response_model=List[UXPageResponse],
)
async def list_pages_route(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_ux_pages_for_model(db, model_id=model_id, owner_id=current_user.id)


@router.get(
    "/pages/{page_id}",
    response_model=UXPageDetailResponse,
)
async def get_page_route(
    page=Depends(_get_owned_page),
):
    return page


@router.put(
    "/pages/{page_id}",
    response_model=UXPageResponse,
)
async def update_page_route(
    data: UXPageUpdate,
    page=Depends(_get_owned_page),
    db: AsyncSession = Depends(get_db),
):
    if "parent_page_id" in data.model_fields_set:
        await _validate_parent_page(
            db,
            data.parent_page_id,
            model_id=page.model_id,
            owner_id=page.owner_id,
            current_page_id=page.id,
        )
    return await update_ux_page(db, page, data)


@router.delete(
    "/pages/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_page_route(
    page=Depends(_get_owned_page),
    db: AsyncSession = Depends(get_db),
):
    await delete_ux_page(db, page)


@router.put(
    "/pages/{page_id}/publish",
    response_model=UXPageResponse,
)
async def publish_page_route(
    data: UXPagePublishRequest,
    page=Depends(_get_owned_page),
    db: AsyncSession = Depends(get_db),
):
    return await publish_ux_page(db, page, data.is_published)


@router.put(
    "/models/{model_id}/pages/reorder",
    response_model=List[UXPageResponse],
)
async def reorder_pages_route(
    model_id: uuid.UUID,
    data: UXPageReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await reorder_ux_pages(db, model_id, current_user.id, data.page_ids)


# -- Card routes ---------------------------------------------------------------

@router.post(
    "/pages/{page_id}/cards",
    response_model=UXPageCardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_card_route(
    data: UXPageCardCreate,
    page=Depends(_get_owned_page),
    db: AsyncSession = Depends(get_db),
):
    return await create_ux_card(db, data, page_id=page.id)


@router.put(
    "/cards/{card_id}",
    response_model=UXPageCardResponse,
)
async def update_card_route(
    data: UXPageCardUpdate,
    card=Depends(_get_owned_card),
    db: AsyncSession = Depends(get_db),
):
    return await update_ux_card(db, card, data)


@router.delete(
    "/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_card_route(
    card=Depends(_get_owned_card),
    db: AsyncSession = Depends(get_db),
):
    await delete_ux_card(db, card)


@router.put(
    "/pages/{page_id}/cards/reorder",
    response_model=List[UXPageCardResponse],
)
async def reorder_cards_route(
    data: UXCardReorderRequest,
    page=Depends(_get_owned_page),
    db: AsyncSession = Depends(get_db),
):
    return await reorder_ux_cards(db, page.id, data.card_ids)


# -- Context selector routes ---------------------------------------------------

@router.post(
    "/pages/{page_id}/context-selectors",
    response_model=UXContextSelectorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_context_selector_route(
    data: UXContextSelectorCreate,
    page=Depends(_get_owned_page),
    db: AsyncSession = Depends(get_db),
):
    return await create_ux_context_selector(db, data, page_id=page.id)


@router.delete(
    "/context-selectors/{selector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_context_selector_route(
    selector=Depends(_get_owned_selector),
    db: AsyncSession = Depends(get_db),
):
    await delete_ux_context_selector(db, selector)
