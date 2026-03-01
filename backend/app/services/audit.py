import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEntry, AuditEventType


async def log_event(
    db: AsyncSession,
    model_id: uuid.UUID,
    event_type: AuditEventType,
    entity_type: str,
    entity_id: str,
    user_id: Optional[uuid.UUID] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEntry:
    entry = AuditEntry(
        model_id=model_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        old_value=old_value,
        new_value=new_value,
        metadata_=metadata,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_audit_log(
    db: AsyncSession,
    model_id: uuid.UUID,
    event_type: Optional[AuditEventType] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[AuditEntry]:
    stmt = select(AuditEntry).where(AuditEntry.model_id == model_id)

    if event_type is not None:
        stmt = stmt.where(AuditEntry.event_type == event_type)
    if entity_type is not None:
        stmt = stmt.where(AuditEntry.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEntry.entity_id == entity_id)
    if user_id is not None:
        stmt = stmt.where(AuditEntry.user_id == user_id)
    if after is not None:
        stmt = stmt.where(AuditEntry.created_at >= after)
    if before is not None:
        stmt = stmt.where(AuditEntry.created_at <= before)

    stmt = stmt.order_by(AuditEntry.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_entity_history(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    limit: int = 20,
) -> List[AuditEntry]:
    stmt = (
        select(AuditEntry)
        .where(AuditEntry.entity_type == entity_type)
        .where(AuditEntry.entity_id == entity_id)
        .order_by(AuditEntry.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_audit_summary(
    db: AsyncSession,
    model_id: uuid.UUID,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
) -> Dict[str, int]:
    stmt = (
        select(AuditEntry.event_type, func.count(AuditEntry.id))
        .where(AuditEntry.model_id == model_id)
    )

    if after is not None:
        stmt = stmt.where(AuditEntry.created_at >= after)
    if before is not None:
        stmt = stmt.where(AuditEntry.created_at <= before)

    stmt = stmt.group_by(AuditEntry.event_type)
    result = await db.execute(stmt)
    rows = result.all()
    return {str(event_type.value): count for event_type, count in rows}


async def purge_old_entries(
    db: AsyncSession,
    model_id: uuid.UUID,
    before_date: datetime,
) -> int:
    stmt = (
        delete(AuditEntry)
        .where(AuditEntry.model_id == model_id)
        .where(AuditEntry.created_at < before_date)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
