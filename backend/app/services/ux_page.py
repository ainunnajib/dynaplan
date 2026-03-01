import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ux_page import UXContextSelector, UXPage, UXPageCard
from app.schemas.ux_page import (
    UXContextSelectorCreate,
    UXPageCardCreate,
    UXPageCardUpdate,
    UXPageCreate,
    UXPageUpdate,
)


# -- UXPage CRUD --------------------------------------------------------------

async def create_ux_page(
    db: AsyncSession,
    data: UXPageCreate,
    model_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> UXPage:
    page = UXPage(
        name=data.name,
        page_type=data.page_type,
        description=data.description,
        layout_config=data.layout_config or {},
        sort_order=data.sort_order,
        model_id=model_id,
        owner_id=owner_id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def get_ux_page_by_id(
    db: AsyncSession, page_id: uuid.UUID
) -> Optional[UXPage]:
    result = await db.execute(
        select(UXPage)
        .where(UXPage.id == page_id)
        .options(
            selectinload(UXPage.cards),
            selectinload(UXPage.context_selectors),
        )
    )
    return result.scalar_one_or_none()


async def list_ux_pages_for_model(
    db: AsyncSession, model_id: uuid.UUID, owner_id: uuid.UUID
) -> List[UXPage]:
    result = await db.execute(
        select(UXPage)
        .where(UXPage.model_id == model_id, UXPage.owner_id == owner_id)
        .order_by(UXPage.sort_order, UXPage.created_at)
    )
    return list(result.scalars().all())


async def update_ux_page(
    db: AsyncSession, page: UXPage, data: UXPageUpdate
) -> UXPage:
    if data.name is not None:
        page.name = data.name
    if data.description is not None:
        page.description = data.description
    if data.layout_config is not None:
        page.layout_config = data.layout_config
    if data.sort_order is not None:
        page.sort_order = data.sort_order
    await db.commit()
    await db.refresh(page)
    return page


async def delete_ux_page(db: AsyncSession, page: UXPage) -> None:
    await db.delete(page)
    await db.commit()


async def publish_ux_page(
    db: AsyncSession, page: UXPage, is_published: bool
) -> UXPage:
    page.is_published = is_published
    await db.commit()
    await db.refresh(page)
    return page


async def reorder_ux_pages(
    db: AsyncSession,
    model_id: uuid.UUID,
    owner_id: uuid.UUID,
    page_ids: List[uuid.UUID],
) -> List[UXPage]:
    result = await db.execute(
        select(UXPage).where(
            UXPage.model_id == model_id,
            UXPage.owner_id == owner_id,
        )
    )
    pages = {p.id: p for p in result.scalars().all()}
    for order, pid in enumerate(page_ids):
        if pid in pages:
            pages[pid].sort_order = order
    await db.commit()
    updated = list(pages.values())
    for page in updated:
        await db.refresh(page)
    updated.sort(key=lambda p: p.sort_order)
    return updated


# -- UXPageCard CRUD -----------------------------------------------------------

async def create_ux_card(
    db: AsyncSession,
    data: UXPageCardCreate,
    page_id: uuid.UUID,
) -> UXPageCard:
    card = UXPageCard(
        page_id=page_id,
        card_type=data.card_type,
        title=data.title,
        config=data.config or {},
        position_x=data.position_x,
        position_y=data.position_y,
        width=data.width,
        height=data.height,
        sort_order=data.sort_order,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def get_ux_card_by_id(
    db: AsyncSession, card_id: uuid.UUID
) -> Optional[UXPageCard]:
    result = await db.execute(
        select(UXPageCard).where(UXPageCard.id == card_id)
    )
    return result.scalar_one_or_none()


async def update_ux_card(
    db: AsyncSession, card: UXPageCard, data: UXPageCardUpdate
) -> UXPageCard:
    if data.title is not None:
        card.title = data.title
    if data.config is not None:
        card.config = data.config
    if data.position_x is not None:
        card.position_x = data.position_x
    if data.position_y is not None:
        card.position_y = data.position_y
    if data.width is not None:
        card.width = data.width
    if data.height is not None:
        card.height = data.height
    if data.sort_order is not None:
        card.sort_order = data.sort_order
    await db.commit()
    await db.refresh(card)
    return card


async def delete_ux_card(db: AsyncSession, card: UXPageCard) -> None:
    await db.delete(card)
    await db.commit()


async def reorder_ux_cards(
    db: AsyncSession,
    page_id: uuid.UUID,
    card_ids: List[uuid.UUID],
) -> List[UXPageCard]:
    result = await db.execute(
        select(UXPageCard).where(UXPageCard.page_id == page_id)
    )
    cards = {c.id: c for c in result.scalars().all()}
    for order, cid in enumerate(card_ids):
        if cid in cards:
            cards[cid].sort_order = order
    await db.commit()
    updated = list(cards.values())
    for card in updated:
        await db.refresh(card)
    updated.sort(key=lambda c: c.sort_order)
    return updated


# -- UXContextSelector CRUD ---------------------------------------------------

async def create_ux_context_selector(
    db: AsyncSession,
    data: UXContextSelectorCreate,
    page_id: uuid.UUID,
) -> UXContextSelector:
    selector = UXContextSelector(
        page_id=page_id,
        dimension_id=data.dimension_id,
        label=data.label,
        allow_multi_select=data.allow_multi_select,
        default_member_id=data.default_member_id,
        sort_order=data.sort_order,
    )
    db.add(selector)
    await db.commit()
    await db.refresh(selector)
    return selector


async def get_ux_context_selector_by_id(
    db: AsyncSession, selector_id: uuid.UUID
) -> Optional[UXContextSelector]:
    result = await db.execute(
        select(UXContextSelector).where(UXContextSelector.id == selector_id)
    )
    return result.scalar_one_or_none()


async def delete_ux_context_selector(
    db: AsyncSession, selector: UXContextSelector
) -> None:
    await db.delete(selector)
    await db.commit()
