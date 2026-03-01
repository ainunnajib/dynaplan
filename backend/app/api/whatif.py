import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.whatif import (
    AssumptionCreate,
    AssumptionResponse,
    ScenarioCompareResult,
    ScenarioCreate,
    ScenarioEvalResult,
    ScenarioResponse,
)
from app.services.whatif import (
    add_assumption,
    compare_to_base,
    create_scenario,
    delete_scenario,
    evaluate_scenario,
    get_scenario,
    list_assumptions,
    list_scenarios,
    promote_scenario,
    remove_assumption,
    _scenario_to_response,
)

router = APIRouter(tags=["whatif"])


# ── Helpers ─────────────────────────────────────────────────────────────────────

async def _get_scenario_or_404(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = await get_scenario(db, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )
    return scenario


# ── Scenario endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario_endpoint(
    model_id: uuid.UUID,
    data: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = await create_scenario(
        db,
        model_id=model_id,
        name=data.name,
        description=data.description,
        base_version_id=data.base_version_id,
        user_id=current_user.id,
    )
    return await _scenario_to_response(db, scenario)


@router.get(
    "/models/{model_id}/scenarios",
    response_model=List[ScenarioResponse],
)
async def list_scenarios_endpoint(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenarios = await list_scenarios(db, model_id=model_id)
    result = []
    for s in scenarios:
        result.append(await _scenario_to_response(db, s))
    return result


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
)
async def get_scenario_endpoint(
    scenario=Depends(_get_scenario_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await _scenario_to_response(db, scenario)


@router.delete(
    "/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scenario_endpoint(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await delete_scenario(db, scenario_id=scenario_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )


# ── Assumption endpoints ────────────────────────────────────────────────────────

@router.post(
    "/scenarios/{scenario_id}/assumptions",
    response_model=AssumptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_assumption_endpoint(
    scenario_id: uuid.UUID,
    data: AssumptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = await get_scenario(db, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )
    assumption = await add_assumption(
        db,
        scenario_id=scenario_id,
        line_item_id=data.line_item_id,
        dimension_key=data.dimension_key,
        original_value=None,
        modified_value=data.modified_value,
        note=data.note,
    )
    return assumption


@router.get(
    "/scenarios/{scenario_id}/assumptions",
    response_model=List[AssumptionResponse],
)
async def list_assumptions_endpoint(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = await get_scenario(db, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )
    return await list_assumptions(db, scenario_id=scenario_id)


@router.delete(
    "/assumptions/{assumption_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_assumption_endpoint(
    assumption_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await remove_assumption(db, assumption_id=assumption_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assumption not found",
        )


# ── Evaluate & compare endpoints ────────────────────────────────────────────────

@router.get(
    "/scenarios/{scenario_id}/evaluate",
    response_model=ScenarioEvalResult,
)
async def evaluate_scenario_endpoint(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await evaluate_scenario(db, scenario_id=scenario_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )
    return result


@router.get(
    "/scenarios/{scenario_id}/compare",
    response_model=ScenarioCompareResult,
)
async def compare_scenario_endpoint(
    scenario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await compare_to_base(db, scenario_id=scenario_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )
    return result


@router.post(
    "/scenarios/{scenario_id}/promote",
    response_model=dict,
)
async def promote_scenario_endpoint(
    scenario_id: uuid.UUID,
    target_version_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await promote_scenario(db, scenario_id=scenario_id, target_version_id=target_version_id)
    if count is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )
    return {"promoted_cells": count}
