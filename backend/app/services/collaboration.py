import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaboration import PresenceSession
from app.schemas.collaboration import PresenceResponse


async def register_presence(
    db: AsyncSession,
    user_id: uuid.UUID,
    model_id: uuid.UUID,
    module_id: Optional[uuid.UUID] = None,
) -> PresenceSession:
    """Create or update a presence session for a user in a model."""
    # Check if session already exists for this user+model
    result = await db.execute(
        select(PresenceSession).where(
            PresenceSession.user_id == user_id,
            PresenceSession.model_id == model_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.module_id = module_id
        existing.last_heartbeat = datetime.now(timezone.utc)
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    session = PresenceSession(
        user_id=user_id,
        model_id=model_id,
        module_id=module_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def update_heartbeat(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> Optional[PresenceSession]:
    """Update the last_heartbeat timestamp for a session."""
    result = await db.execute(
        select(PresenceSession).where(PresenceSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    session.last_heartbeat = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def update_cursor(
    db: AsyncSession,
    session_id: uuid.UUID,
    cell_ref: Optional[str],
) -> Optional[PresenceSession]:
    """Update the cursor position for a session."""
    result = await db.execute(
        select(PresenceSession).where(PresenceSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    session.cursor_cell = cell_ref
    session.last_heartbeat = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def remove_presence(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> bool:
    """Delete a presence session. Returns True if deleted, False if not found."""
    result = await db.execute(
        select(PresenceSession).where(PresenceSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return False
    await db.delete(session)
    await db.commit()
    return True


async def get_active_users(
    db: AsyncSession,
    model_id: uuid.UUID,
    module_id: Optional[uuid.UUID] = None,
    active_seconds: int = 60,
) -> List[PresenceSession]:
    """List users active in the last `active_seconds` seconds."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=active_seconds)
    stmt = select(PresenceSession).where(
        PresenceSession.model_id == model_id,
        PresenceSession.last_heartbeat >= cutoff,
    )
    if module_id is not None:
        stmt = stmt.where(PresenceSession.module_id == module_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session_by_id(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> Optional[PresenceSession]:
    """Get a single presence session by its ID."""
    result = await db.execute(
        select(PresenceSession).where(PresenceSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def cleanup_stale_sessions(
    db: AsyncSession,
    timeout_seconds: int = 120,
) -> int:
    """Remove sessions that have not had a heartbeat within timeout_seconds.
    Returns the number of sessions removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    result = await db.execute(
        select(PresenceSession).where(
            PresenceSession.last_heartbeat < cutoff
        )
    )
    stale = result.scalars().all()
    count = len(stale)
    for session in stale:
        await db.delete(session)
    await db.commit()
    return count


def build_presence_response(session: PresenceSession) -> PresenceResponse:
    """Convert a PresenceSession ORM object to a PresenceResponse schema."""
    user_email = None
    user_full_name = None
    if session.user is not None:
        user_email = session.user.email
        user_full_name = session.user.full_name
    return PresenceResponse(
        id=session.id,
        user_id=session.user_id,
        model_id=session.model_id,
        module_id=session.module_id,
        connected_at=session.connected_at,
        last_heartbeat=session.last_heartbeat,
        cursor_cell=session.cursor_cell,
        user_email=user_email,
        user_full_name=user_full_name,
    )
