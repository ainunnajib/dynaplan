import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.whatif import WhatIfAssumption, WhatIfScenario
from app.schemas.whatif import (
    DiffCell,
    EvaluatedCell,
    ScenarioCompareResult,
    ScenarioEvalResult,
    ScenarioResponse,
)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _cell_value_as_str(cell: CellValue) -> Optional[str]:
    """Return a string representation of a cell's value."""
    if cell.value_number is not None:
        return str(cell.value_number)
    if cell.value_text is not None:
        return cell.value_text
    if cell.value_boolean is not None:
        return str(cell.value_boolean)
    return None


async def _count_assumptions(db: AsyncSession, scenario_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(WhatIfAssumption.scenario_id == scenario_id)
    )
    return result.scalar_one()


async def _scenario_to_response(db: AsyncSession, scenario: WhatIfScenario) -> ScenarioResponse:
    count = await _count_assumptions(db, scenario.id)
    return ScenarioResponse(
        id=scenario.id,
        model_id=scenario.model_id,
        name=scenario.name,
        description=scenario.description,
        base_version_id=scenario.base_version_id,
        created_by=scenario.created_by,
        is_active=scenario.is_active,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        assumption_count=count,
    )


# ── Scenario CRUD ────────────────────────────────────────────────────────────────

async def create_scenario(
    db: AsyncSession,
    model_id: uuid.UUID,
    name: str,
    description: Optional[str],
    base_version_id: Optional[uuid.UUID],
    user_id: uuid.UUID,
) -> WhatIfScenario:
    scenario = WhatIfScenario(
        model_id=model_id,
        name=name,
        description=description,
        base_version_id=base_version_id,
        created_by=user_id,
        is_active=True,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def list_scenarios(
    db: AsyncSession, model_id: uuid.UUID
) -> List[WhatIfScenario]:
    result = await db.execute(
        select(WhatIfScenario)
        .where(WhatIfScenario.model_id == model_id, WhatIfScenario.is_active.is_(True))
        .order_by(WhatIfScenario.created_at)
    )
    return list(result.scalars().all())


async def get_scenario(
    db: AsyncSession, scenario_id: uuid.UUID
) -> Optional[WhatIfScenario]:
    result = await db.execute(
        select(WhatIfScenario).where(WhatIfScenario.id == scenario_id)
    )
    return result.scalar_one_or_none()


async def delete_scenario(db: AsyncSession, scenario_id: uuid.UUID) -> bool:
    """Soft delete: set is_active=False. Returns True if found, False otherwise."""
    result = await db.execute(
        select(WhatIfScenario).where(WhatIfScenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        return False
    scenario.is_active = False
    await db.commit()
    return True


# ── Assumption CRUD ──────────────────────────────────────────────────────────────

async def add_assumption(
    db: AsyncSession,
    scenario_id: uuid.UUID,
    line_item_id: uuid.UUID,
    dimension_key: str,
    original_value: Optional[str],
    modified_value: str,
    note: Optional[str] = None,
) -> WhatIfAssumption:
    """Add or update an assumption. If one already exists for the same
    scenario/line_item/dimension_key, it is updated in-place."""
    result = await db.execute(
        select(WhatIfAssumption).where(
            WhatIfAssumption.scenario_id == scenario_id,
            WhatIfAssumption.line_item_id == line_item_id,
            WhatIfAssumption.dimension_key == dimension_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.modified_value = modified_value
        existing.original_value = original_value
        if note is not None:
            existing.note = note
        await db.commit()
        await db.refresh(existing)
        return existing

    assumption = WhatIfAssumption(
        scenario_id=scenario_id,
        line_item_id=line_item_id,
        dimension_key=dimension_key,
        original_value=original_value,
        modified_value=modified_value,
        note=note,
    )
    db.add(assumption)
    await db.commit()
    await db.refresh(assumption)
    return assumption


async def remove_assumption(
    db: AsyncSession, assumption_id: uuid.UUID
) -> bool:
    """Delete an assumption by id. Returns True if found and deleted."""
    result = await db.execute(
        select(WhatIfAssumption).where(WhatIfAssumption.id == assumption_id)
    )
    assumption = result.scalar_one_or_none()
    if assumption is None:
        return False
    await db.delete(assumption)
    await db.commit()
    return True


async def list_assumptions(
    db: AsyncSession, scenario_id: uuid.UUID
) -> List[WhatIfAssumption]:
    result = await db.execute(
        select(WhatIfAssumption)
        .where(WhatIfAssumption.scenario_id == scenario_id)
        .order_by(WhatIfAssumption.created_at)
    )
    return list(result.scalars().all())


async def get_assumption(
    db: AsyncSession, assumption_id: uuid.UUID
) -> Optional[WhatIfAssumption]:
    result = await db.execute(
        select(WhatIfAssumption).where(WhatIfAssumption.id == assumption_id)
    )
    return result.scalar_one_or_none()


# ── Evaluation & comparison ──────────────────────────────────────────────────────

async def evaluate_scenario(
    db: AsyncSession, scenario_id: uuid.UUID
) -> Optional[ScenarioEvalResult]:
    """Get the effective cell values: start from base version cells, overlay assumptions.

    The base version cells are CellValue rows whose dimension_key contains the
    base_version_id string. Assumptions are then overlaid on top of those cells.
    Returns None if the scenario is not found.
    """
    scenario = await get_scenario(db, scenario_id)
    if scenario is None:
        return None

    assumptions = await list_assumptions(db, scenario_id)

    # Build assumption lookup: (line_item_id, dimension_key) -> modified_value
    assumption_map: Dict[Any, str] = {}
    for assumption in assumptions:
        key = (str(assumption.line_item_id), assumption.dimension_key)
        assumption_map[key] = assumption.modified_value

    cells: List[EvaluatedCell] = []

    if scenario.base_version_id is not None:
        # Fetch all cells that have the base_version_id embedded in their dimension_key
        version_str = str(scenario.base_version_id)
        result = await db.execute(
            select(CellValue).where(
                CellValue.dimension_key.contains(version_str)
            )
        )
        base_cells = list(result.scalars().all())

        seen_keys: set = set()
        for cell in base_cells:
            k = (str(cell.line_item_id), cell.dimension_key)
            seen_keys.add(k)
            if k in assumption_map:
                cells.append(EvaluatedCell(
                    line_item_id=cell.line_item_id,
                    dimension_key=cell.dimension_key,
                    value=assumption_map[k],
                    is_modified=True,
                ))
            else:
                cells.append(EvaluatedCell(
                    line_item_id=cell.line_item_id,
                    dimension_key=cell.dimension_key,
                    value=_cell_value_as_str(cell),
                    is_modified=False,
                ))

        # Add assumptions whose keys were not in the base cells
        for assumption in assumptions:
            k = (str(assumption.line_item_id), assumption.dimension_key)
            if k not in seen_keys:
                cells.append(EvaluatedCell(
                    line_item_id=assumption.line_item_id,
                    dimension_key=assumption.dimension_key,
                    value=assumption.modified_value,
                    is_modified=True,
                ))
    else:
        # No base version — return only assumption cells
        for assumption in assumptions:
            cells.append(EvaluatedCell(
                line_item_id=assumption.line_item_id,
                dimension_key=assumption.dimension_key,
                value=assumption.modified_value,
                is_modified=True,
            ))

    return ScenarioEvalResult(scenario_id=scenario_id, cells=cells)


async def compare_to_base(
    db: AsyncSession, scenario_id: uuid.UUID
) -> Optional[ScenarioCompareResult]:
    """Return only cells that differ from the base version.

    Returns None if scenario not found.
    """
    scenario = await get_scenario(db, scenario_id)
    if scenario is None:
        return None

    assumptions = await list_assumptions(db, scenario_id)

    diffs: List[DiffCell] = []
    for assumption in assumptions:
        diffs.append(DiffCell(
            line_item_id=assumption.line_item_id,
            dimension_key=assumption.dimension_key,
            original_value=assumption.original_value,
            modified_value=assumption.modified_value,
        ))

    return ScenarioCompareResult(scenario_id=scenario_id, diffs=diffs)


async def promote_scenario(
    db: AsyncSession,
    scenario_id: uuid.UUID,
    target_version_id: uuid.UUID,
) -> Optional[int]:
    """Write scenario assumptions into a real version's cells.

    For each assumption, we look for an existing CellValue whose dimension_key
    contains the target_version_id string and has the same line_item_id.  If
    found, its numeric/text value is updated to the modified_value.  If not
    found, a new CellValue is inserted using the assumption's dimension_key
    but with the base_version_id segment replaced by target_version_id.

    Returns the number of cells written, or None if the scenario is not found.
    """
    scenario = await get_scenario(db, scenario_id)
    if scenario is None:
        return None

    assumptions = await list_assumptions(db, scenario_id)
    target_str = str(target_version_id)
    base_str = str(scenario.base_version_id) if scenario.base_version_id else None

    count = 0
    for assumption in assumptions:
        # Derive the target dimension_key from the assumption's dimension_key
        if base_str and base_str in assumption.dimension_key:
            target_dim_key = assumption.dimension_key.replace(base_str, target_str)
        else:
            target_dim_key = assumption.dimension_key

        # Parse modified_value to number or text
        modified_str = assumption.modified_value
        try:
            value_number: Optional[float] = float(modified_str)
            value_text: Optional[str] = None
        except (ValueError, TypeError):
            value_number = None
            value_text = modified_str

        # Try to find existing cell
        result = await db.execute(
            select(CellValue).where(
                CellValue.line_item_id == assumption.line_item_id,
                CellValue.dimension_key == target_dim_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.value_number = value_number
            existing.value_text = value_text
            existing.value_boolean = None
        else:
            new_cell = CellValue(
                line_item_id=assumption.line_item_id,
                dimension_key=target_dim_key,
                value_number=value_number,
                value_text=value_text,
                value_boolean=None,
            )
            db.add(new_cell)

        count += 1

    await db.commit()
    return count
