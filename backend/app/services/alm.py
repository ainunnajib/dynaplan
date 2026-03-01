import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alm import (
    ALMEnvironment,
    EnvironmentType,
    PromotionRecord,
    PromotionStatus,
    RevisionTag,
)
from app.schemas.alm import (
    EnvironmentCreate,
    EnvironmentUpdate,
    LockRequest,
    PromotionCreate,
    RevisionTagCreate,
    TagComparisonResponse,
)


# ---------------------------------------------------------------------------
# Environment CRUD
# ---------------------------------------------------------------------------


async def create_environment(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: EnvironmentCreate,
) -> ALMEnvironment:
    env = ALMEnvironment(
        model_id=model_id,
        env_type=EnvironmentType(data.env_type),
        name=data.name,
        description=data.description,
        source_env_id=data.source_env_id,
    )
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


async def get_environment_by_id(
    db: AsyncSession, env_id: uuid.UUID
) -> Optional[ALMEnvironment]:
    result = await db.execute(
        select(ALMEnvironment).where(ALMEnvironment.id == env_id)
    )
    return result.scalar_one_or_none()


async def list_environments_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[ALMEnvironment]:
    result = await db.execute(
        select(ALMEnvironment)
        .where(ALMEnvironment.model_id == model_id)
        .order_by(ALMEnvironment.created_at.asc())
    )
    return list(result.scalars().all())


async def update_environment(
    db: AsyncSession, env: ALMEnvironment, data: EnvironmentUpdate
) -> ALMEnvironment:
    if data.name is not None:
        env.name = data.name
    if data.description is not None:
        env.description = data.description
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


async def delete_environment(db: AsyncSession, env: ALMEnvironment) -> None:
    await db.delete(env)
    await db.commit()


# ---------------------------------------------------------------------------
# Lock / Unlock
# ---------------------------------------------------------------------------


async def set_environment_lock(
    db: AsyncSession, env: ALMEnvironment, data: LockRequest
) -> ALMEnvironment:
    env.is_locked = data.is_locked
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


# ---------------------------------------------------------------------------
# Revision Tags
# ---------------------------------------------------------------------------


async def create_revision_tag(
    db: AsyncSession,
    env_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RevisionTagCreate,
) -> RevisionTag:
    tag = RevisionTag(
        environment_id=env_id,
        tag_name=data.tag_name,
        description=data.description,
        created_by=user_id,
        snapshot_data=data.snapshot_data if data.snapshot_data else {},
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def get_revision_tag_by_id(
    db: AsyncSession, tag_id: uuid.UUID
) -> Optional[RevisionTag]:
    result = await db.execute(
        select(RevisionTag).where(RevisionTag.id == tag_id)
    )
    return result.scalar_one_or_none()


async def list_revision_tags(
    db: AsyncSession, env_id: uuid.UUID
) -> List[RevisionTag]:
    result = await db.execute(
        select(RevisionTag)
        .where(RevisionTag.environment_id == env_id)
        .order_by(RevisionTag.created_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


async def initiate_promotion(
    db: AsyncSession,
    source_env_id: uuid.UUID,
    user_id: uuid.UUID,
    data: PromotionCreate,
) -> PromotionRecord:
    record = PromotionRecord(
        source_env_id=source_env_id,
        target_env_id=data.target_env_id,
        revision_tag_id=data.revision_tag_id,
        promoted_by=user_id,
        status=PromotionStatus.pending,
        change_summary=data.change_summary if data.change_summary else {},
        started_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_promotion_by_id(
    db: AsyncSession, promotion_id: uuid.UUID
) -> Optional[PromotionRecord]:
    result = await db.execute(
        select(PromotionRecord).where(PromotionRecord.id == promotion_id)
    )
    return result.scalar_one_or_none()


async def list_promotions_for_env(
    db: AsyncSession, env_id: uuid.UUID
) -> List[PromotionRecord]:
    result = await db.execute(
        select(PromotionRecord)
        .where(PromotionRecord.source_env_id == env_id)
        .order_by(PromotionRecord.created_at.desc())
    )
    return list(result.scalars().all())


async def complete_promotion(
    db: AsyncSession, record: PromotionRecord
) -> PromotionRecord:
    if record.status not in (PromotionStatus.pending, PromotionStatus.in_progress):
        raise ValueError(
            f"Cannot complete promotion with status {record.status.value}"
        )
    record.status = PromotionStatus.completed
    record.completed_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def fail_promotion(
    db: AsyncSession, record: PromotionRecord
) -> PromotionRecord:
    if record.status not in (PromotionStatus.pending, PromotionStatus.in_progress):
        raise ValueError(
            f"Cannot fail promotion with status {record.status.value}"
        )
    record.status = PromotionStatus.failed
    record.completed_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Tag comparison
# ---------------------------------------------------------------------------


def _diff_dicts(old: dict, new: dict) -> Dict:
    """Shallow diff two dicts, returning added/removed/modified keys."""
    added = {}
    removed = {}
    modified = {}

    all_keys = set(list(old.keys()) + list(new.keys()))
    for key in all_keys:
        if key not in old:
            added[key] = new[key]
        elif key not in new:
            removed[key] = old[key]
        elif old[key] != new[key]:
            modified[key] = {"old": old[key], "new": new[key]}

    return {"added": added, "removed": removed, "modified": modified}


async def compare_revision_tags(
    db: AsyncSession,
    tag_1: RevisionTag,
    tag_2: RevisionTag,
) -> TagComparisonResponse:
    snap_1 = tag_1.snapshot_data if tag_1.snapshot_data else {}
    snap_2 = tag_2.snapshot_data if tag_2.snapshot_data else {}
    diff = _diff_dicts(snap_1, snap_2)
    return TagComparisonResponse(
        tag_1_id=tag_1.id,
        tag_1_name=tag_1.tag_name,
        tag_2_id=tag_2.id,
        tag_2_name=tag_2.tag_name,
        added=diff["added"],
        removed=diff["removed"],
        modified=diff["modified"],
    )
