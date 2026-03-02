import uuid
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.saved_view import SavedView
from app.schemas.saved_view import SavedViewCreate, SavedViewUpdate


async def _clear_default_for_scope(
    db: AsyncSession,
    module_id: uuid.UUID,
    user_id: uuid.UUID,
    exclude_saved_view_id: Optional[uuid.UUID] = None,
) -> None:
    stmt = (
        update(SavedView)
        .where(
            SavedView.module_id == module_id,
            SavedView.user_id == user_id,
            SavedView.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if exclude_saved_view_id is not None:
        stmt = stmt.where(SavedView.id != exclude_saved_view_id)
    await db.execute(stmt)


async def create_saved_view(
    db: AsyncSession,
    module_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SavedViewCreate,
) -> SavedView:
    name = data.name.strip()
    if not name:
        raise ValueError("Saved view name is required")

    if data.is_default:
        await _clear_default_for_scope(db, module_id=module_id, user_id=user_id)

    saved_view = SavedView(
        user_id=user_id,
        module_id=module_id,
        name=name,
        view_config=data.view_config.model_dump(mode="json"),
        is_default=data.is_default,
    )
    db.add(saved_view)
    await db.commit()
    created = await get_saved_view_by_id(db, saved_view.id)
    return created if created is not None else saved_view


async def list_saved_views_for_module(
    db: AsyncSession,
    module_id: uuid.UUID,
    user_id: uuid.UUID,
) -> List[SavedView]:
    result = await db.execute(
        select(SavedView)
        .where(
            SavedView.module_id == module_id,
            SavedView.user_id == user_id,
        )
        .options(
            selectinload(SavedView.module),
            selectinload(SavedView.user),
        )
        .order_by(
            SavedView.is_default.desc(),
            SavedView.created_at,
        )
    )
    return list(result.scalars().all())


async def get_saved_view_by_id(
    db: AsyncSession,
    saved_view_id: uuid.UUID,
) -> Optional[SavedView]:
    result = await db.execute(
        select(SavedView)
        .where(SavedView.id == saved_view_id)
        .options(
            selectinload(SavedView.module),
            selectinload(SavedView.user),
        )
    )
    return result.scalar_one_or_none()


async def update_saved_view(
    db: AsyncSession,
    saved_view: SavedView,
    data: SavedViewUpdate,
) -> SavedView:
    if "name" in data.model_fields_set and data.name is not None:
        name = data.name.strip()
        if not name:
            raise ValueError("Saved view name is required")
        saved_view.name = name

    if "view_config" in data.model_fields_set and data.view_config is not None:
        saved_view.view_config = data.view_config.model_dump(mode="json")

    if "is_default" in data.model_fields_set and data.is_default is not None:
        if data.is_default:
            await _clear_default_for_scope(
                db,
                module_id=saved_view.module_id,
                user_id=saved_view.user_id,
                exclude_saved_view_id=saved_view.id,
            )
        saved_view.is_default = data.is_default

    await db.commit()
    updated = await get_saved_view_by_id(db, saved_view.id)
    return updated if updated is not None else saved_view


async def set_saved_view_as_default(
    db: AsyncSession,
    saved_view: SavedView,
) -> SavedView:
    await _clear_default_for_scope(
        db,
        module_id=saved_view.module_id,
        user_id=saved_view.user_id,
        exclude_saved_view_id=saved_view.id,
    )
    saved_view.is_default = True
    await db.commit()
    updated = await get_saved_view_by_id(db, saved_view.id)
    return updated if updated is not None else saved_view


async def delete_saved_view(
    db: AsyncSession,
    saved_view: SavedView,
) -> None:
    await db.delete(saved_view)
    await db.commit()
