"""
Calculation Cache Service — F031

Provides get/set/invalidate operations for cached computed values,
with dependency-aware cascade invalidation and bulk operations.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc_cache import CalcCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_formula_hash(formula: str) -> str:
    """Return the SHA-256 hex digest of a formula string."""
    return hashlib.sha256(formula.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

async def get_cached_value(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_key: str,
) -> Optional[CalcCache]:
    """
    Return the cache entry if it exists, is valid, and has not expired.
    Returns None on a cache miss.
    """
    result = await db.execute(
        select(CalcCache).where(
            CalcCache.line_item_id == line_item_id,
            CalcCache.dimension_key == dimension_key,
            CalcCache.is_valid == True,  # noqa: E712
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        return None

    # Check expiry
    if entry.expires_at is not None:
        now = _now_utc()
        # Make expires_at timezone-aware for comparison if needed
        exp = entry.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            return None

    return entry


async def get_stale_entries(
    db: AsyncSession,
    model_id: uuid.UUID,
    limit: int = 100,
) -> List[CalcCache]:
    """Return invalid (stale) cache entries for a model, up to `limit`."""
    result = await db.execute(
        select(CalcCache)
        .where(
            CalcCache.model_id == model_id,
            CalcCache.is_valid == False,  # noqa: E712
        )
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

async def set_cached_value(
    db: AsyncSession,
    model_id: uuid.UUID,
    line_item_id: uuid.UUID,
    dimension_key: str,
    value: Any,
    formula_hash: str,
    expires_at: Optional[datetime] = None,
) -> CalcCache:
    """
    Upsert a cache entry: update existing or insert new.
    The computed_value is stored as its string representation.
    """
    computed_value = str(value) if value is not None else None

    result = await db.execute(
        select(CalcCache).where(
            CalcCache.line_item_id == line_item_id,
            CalcCache.dimension_key == dimension_key,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.computed_value = computed_value
        existing.formula_hash = formula_hash
        existing.is_valid = True
        existing.computed_at = _now_utc()
        existing.expires_at = expires_at
        existing.model_id = model_id
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        entry = CalcCache(
            model_id=model_id,
            line_item_id=line_item_id,
            dimension_key=dimension_key,
            computed_value=computed_value,
            formula_hash=formula_hash,
            is_valid=True,
            computed_at=_now_utc(),
            expires_at=expires_at,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry


async def bulk_set_cache(
    db: AsyncSession,
    model_id: uuid.UUID,
    entries: List[Dict],
) -> List[CalcCache]:
    """
    Batch insert/update cache entries.

    Each entry dict must have keys: line_item_id, dimension_key, value,
    formula_hash. Optionally: expires_at.
    """
    results = []
    for entry_data in entries:
        entry = await set_cached_value(
            db=db,
            model_id=model_id,
            line_item_id=entry_data["line_item_id"],
            dimension_key=entry_data["dimension_key"],
            value=entry_data.get("value"),
            formula_hash=entry_data["formula_hash"],
            expires_at=entry_data.get("expires_at"),
        )
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

async def invalidate_cache(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_key: Optional[str] = None,
) -> int:
    """
    Mark cache entries as invalid.

    If dimension_key is provided, invalidate only that specific entry.
    If dimension_key is None, invalidate all entries for the line item.

    Returns the number of entries invalidated.
    """
    stmt = (
        update(CalcCache)
        .where(CalcCache.line_item_id == line_item_id)
    )
    if dimension_key is not None:
        stmt = stmt.where(CalcCache.dimension_key == dimension_key)

    stmt = stmt.values(is_valid=False)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def invalidate_dependents(
    db: AsyncSession,
    model_id: uuid.UUID,
    line_item_id: uuid.UUID,
    dependency_graph: Any,
) -> int:
    """
    Use the dependency graph to invalidate all downstream cached values
    (including the given line_item_id itself).

    dependency_graph must be an instance of DependencyGraph (or compatible
    object) with a get_recalc_order(changed_nodes) method that returns
    a list of string node IDs.

    Returns total number of entries invalidated.
    """
    changed = {str(line_item_id)}
    try:
        affected_ids = dependency_graph.get_recalc_order(changed)
    except Exception:
        # If the graph raises (e.g. cycle), fall back to just this item
        affected_ids = list(changed)

    total = 0
    for node_id_str in affected_ids:
        try:
            node_uuid = uuid.UUID(node_id_str)
        except ValueError:
            continue
        count = await invalidate_cache(db, node_uuid)
        total += count
    return total


# ---------------------------------------------------------------------------
# Stats & maintenance
# ---------------------------------------------------------------------------

async def get_cache_stats(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Dict:
    """
    Return cache statistics for a model:
    total_entries, valid_count, invalid_count, oldest_entry, newest_entry.
    """
    # Total count
    total_result = await db.execute(
        select(func.count(CalcCache.id)).where(CalcCache.model_id == model_id)
    )
    total = total_result.scalar() or 0

    # Valid count
    valid_result = await db.execute(
        select(func.count(CalcCache.id)).where(
            CalcCache.model_id == model_id,
            CalcCache.is_valid == True,  # noqa: E712
        )
    )
    valid_count = valid_result.scalar() or 0

    # Oldest entry
    oldest_result = await db.execute(
        select(func.min(CalcCache.computed_at)).where(CalcCache.model_id == model_id)
    )
    oldest_entry = oldest_result.scalar()

    # Newest entry
    newest_result = await db.execute(
        select(func.max(CalcCache.computed_at)).where(CalcCache.model_id == model_id)
    )
    newest_entry = newest_result.scalar()

    return {
        "total_entries": total,
        "valid_count": valid_count,
        "invalid_count": total - valid_count,
        "oldest_entry": oldest_entry,
        "newest_entry": newest_entry,
    }


async def clear_cache(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> int:
    """
    Delete all cache entries for a model.
    Returns the number of entries deleted.
    """
    result = await db.execute(
        delete(CalcCache).where(CalcCache.model_id == model_id)
    )
    await db.commit()
    return result.rowcount


async def recalculate_stale(
    db: AsyncSession,
    model_id: uuid.UUID,
    batch_size: int = 50,
) -> Dict:
    """
    Recalculate a batch of stale (invalid) entries.

    This is a placeholder implementation: it marks stale entries as valid
    with a dummy recalculation. In a full implementation this would invoke
    the formula engine for each stale entry.

    Returns: {"entries_recalculated": int, "entries_remaining": int}
    """
    stale = await get_stale_entries(db, model_id, limit=batch_size)
    recalculated = 0

    for entry in stale:
        # Placeholder: mark as valid without re-evaluating formula
        entry.is_valid = True
        entry.computed_at = _now_utc()
        recalculated += 1

    if stale:
        await db.commit()

    # Count remaining stale entries
    remaining_result = await db.execute(
        select(func.count(CalcCache.id)).where(
            CalcCache.model_id == model_id,
            CalcCache.is_valid == False,  # noqa: E712
        )
    )
    remaining = remaining_result.scalar() or 0

    return {
        "entries_recalculated": recalculated,
        "entries_remaining": remaining,
    }
