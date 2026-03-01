import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.dca import (
    AccessLevel,
    DCAConfig,
    SelectiveAccessGrant,
    SelectiveAccessRule,
)


# ---------------------------------------------------------------------------
# Selective Access Rules — CRUD
# ---------------------------------------------------------------------------

async def create_selective_access_rule(
    db: AsyncSession,
    model_id: uuid.UUID,
    name: str,
    dimension_id: uuid.UUID,
    description: Optional[str] = None,
) -> SelectiveAccessRule:
    """Create a new selective access rule for a model."""
    rule = SelectiveAccessRule(
        model_id=model_id,
        name=name,
        dimension_id=dimension_id,
        description=description,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def get_selective_access_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> Optional[SelectiveAccessRule]:
    """Get a selective access rule by ID."""
    result = await db.execute(
        select(SelectiveAccessRule).where(SelectiveAccessRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def list_selective_access_rules(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[SelectiveAccessRule]:
    """List all selective access rules for a model."""
    result = await db.execute(
        select(SelectiveAccessRule).where(SelectiveAccessRule.model_id == model_id)
    )
    return list(result.scalars().all())


async def delete_selective_access_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> bool:
    """Delete a selective access rule. Returns True if deleted."""
    rule = await get_selective_access_rule(db, rule_id)
    if rule is None:
        return False
    await db.delete(rule)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Selective Access Grants — CRUD
# ---------------------------------------------------------------------------

async def create_selective_access_grant(
    db: AsyncSession,
    rule_id: uuid.UUID,
    user_id: uuid.UUID,
    dimension_item_id: uuid.UUID,
    access_level: AccessLevel = AccessLevel.read,
) -> SelectiveAccessGrant:
    """Create a selective access grant within a rule."""
    grant = SelectiveAccessGrant(
        rule_id=rule_id,
        user_id=user_id,
        dimension_item_id=dimension_item_id,
        access_level=access_level,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


async def get_selective_access_grant(
    db: AsyncSession,
    grant_id: uuid.UUID,
) -> Optional[SelectiveAccessGrant]:
    """Get a grant by ID."""
    result = await db.execute(
        select(SelectiveAccessGrant).where(SelectiveAccessGrant.id == grant_id)
    )
    return result.scalar_one_or_none()


async def list_grants_for_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> List[SelectiveAccessGrant]:
    """List all grants for a rule."""
    result = await db.execute(
        select(SelectiveAccessGrant).where(SelectiveAccessGrant.rule_id == rule_id)
    )
    return list(result.scalars().all())


async def delete_selective_access_grant(
    db: AsyncSession,
    grant_id: uuid.UUID,
) -> bool:
    """Delete a grant. Returns True if deleted."""
    grant = await get_selective_access_grant(db, grant_id)
    if grant is None:
        return False
    await db.delete(grant)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# DCA Config — CRUD
# ---------------------------------------------------------------------------

async def create_dca_config(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    read_driver_line_item_id: Optional[uuid.UUID] = None,
    write_driver_line_item_id: Optional[uuid.UUID] = None,
) -> DCAConfig:
    """Create or update a DCA configuration for a line item."""
    result = await db.execute(
        select(DCAConfig).where(DCAConfig.line_item_id == line_item_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.read_driver_line_item_id = read_driver_line_item_id
        existing.write_driver_line_item_id = write_driver_line_item_id
        await db.commit()
        await db.refresh(existing)
        return existing

    config = DCAConfig(
        line_item_id=line_item_id,
        read_driver_line_item_id=read_driver_line_item_id,
        write_driver_line_item_id=write_driver_line_item_id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def get_dca_config(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> Optional[DCAConfig]:
    """Get DCA config for a line item."""
    result = await db.execute(
        select(DCAConfig).where(DCAConfig.line_item_id == line_item_id)
    )
    return result.scalar_one_or_none()


async def delete_dca_config(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> bool:
    """Delete DCA config for a line item. Returns True if deleted."""
    config = await get_dca_config(db, line_item_id)
    if config is None:
        return False
    await db.delete(config)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# DCA Driver Evaluation
# ---------------------------------------------------------------------------

async def evaluate_dca_driver(
    db: AsyncSession,
    driver_line_item_id: uuid.UUID,
    dimension_key: str,
) -> bool:
    """Read the boolean driver value for a given dimension key.

    Returns True if the driver cell value is truthy, False otherwise.
    If no cell value exists, returns True (permissive default).
    """
    result = await db.execute(
        select(CellValue).where(
            CellValue.line_item_id == driver_line_item_id,
            CellValue.dimension_key == dimension_key,
        )
    )
    cell = result.scalar_one_or_none()
    if cell is None:
        return True  # No driver value means access is allowed by default

    # Check boolean value first, then number (non-zero = True), then text
    if cell.value_boolean is not None:
        return cell.value_boolean
    if cell.value_number is not None:
        return cell.value_number != 0
    if cell.value_text is not None:
        return cell.value_text.lower() in ("true", "yes", "1")
    return True


# ---------------------------------------------------------------------------
# Selective Access Check
# ---------------------------------------------------------------------------

async def get_accessible_items(
    db: AsyncSession,
    user_id: uuid.UUID,
    dimension_id: uuid.UUID,
) -> List[dict]:
    """List dimension items a user can access through selective access grants.

    Returns a list of dicts with dimension_item_id and access_level.
    If no grants exist for this user/dimension, returns empty list (meaning
    no selective access restrictions apply — caller should grant full access).
    """
    result = await db.execute(
        select(SelectiveAccessGrant).join(SelectiveAccessRule).where(
            SelectiveAccessRule.dimension_id == dimension_id,
            SelectiveAccessGrant.user_id == user_id,
        )
    )
    grants = list(result.scalars().all())
    return [
        {
            "dimension_item_id": str(g.dimension_item_id),
            "access_level": g.access_level.value,
        }
        for g in grants
    ]


async def _get_grants_for_user_and_dimension_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    dimension_key: str,
) -> List[SelectiveAccessGrant]:
    """Find selective access grants that apply to any dimension item in the key.

    The dimension_key is a pipe-separated string of dimension item UUIDs.
    """
    item_ids_str = dimension_key.split("|")
    item_ids = []
    for s in item_ids_str:
        s = s.strip()
        if s:
            try:
                item_ids.append(uuid.UUID(s))
            except ValueError:
                continue

    if not item_ids:
        return []

    result = await db.execute(
        select(SelectiveAccessGrant).where(
            SelectiveAccessGrant.user_id == user_id,
            SelectiveAccessGrant.dimension_item_id.in_(item_ids),
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Combined Access Check
# ---------------------------------------------------------------------------

async def check_cell_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    line_item_id: uuid.UUID,
    dimension_key: str,
) -> dict:
    """Combine selective access + DCA driver values to determine cell access.

    Returns dict with can_read, can_write, and reason.

    Logic:
    1. Check selective access grants for the dimension items in the key.
       - If grants exist and the most restrictive is 'none', deny all.
       - If grants exist and 'write' is present, allow read+write (selective).
       - If grants exist and only 'read', allow read only.
       - If no grants exist, selective access is not restricting (allow all).
    2. Check DCA config for the line item.
       - If a read driver exists and evaluates to False, deny read (and write).
       - If a write driver exists and evaluates to False, deny write.
    3. Combine: both selective access and DCA must allow the operation.
    """
    can_read = True
    can_write = True
    reasons = []

    # Step 1: Selective access
    grants = await _get_grants_for_user_and_dimension_key(db, user_id, dimension_key)
    if grants:
        access_levels = [g.access_level for g in grants]
        if AccessLevel.none in access_levels:
            can_read = False
            can_write = False
            reasons.append("Selective access denies access to dimension item")
        else:
            # Check if any grant allows write
            has_write = any(al == AccessLevel.write for al in access_levels)
            if not has_write:
                can_write = False
                reasons.append("Selective access grants read-only")

    # Step 2: DCA drivers
    dca_config = await get_dca_config(db, line_item_id)
    if dca_config is not None:
        if dca_config.read_driver_line_item_id is not None:
            read_allowed = await evaluate_dca_driver(
                db, dca_config.read_driver_line_item_id, dimension_key
            )
            if not read_allowed:
                can_read = False
                can_write = False
                reasons.append("DCA read driver denies access")

        if can_read and dca_config.write_driver_line_item_id is not None:
            write_allowed = await evaluate_dca_driver(
                db, dca_config.write_driver_line_item_id, dimension_key
            )
            if not write_allowed:
                can_write = False
                reasons.append("DCA write driver denies write access")

    if not reasons:
        reasons.append("Full access granted")

    return {
        "can_read": can_read,
        "can_write": can_write,
        "reason": "; ".join(reasons),
    }
