import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dca import (
    CellAccessCheckResponse,
    DCAConfigCreate,
    DCAConfigResponse,
    SelectiveAccessGrantCreate,
    SelectiveAccessGrantResponse,
    SelectiveAccessRuleCreate,
    SelectiveAccessRuleResponse,
)
from app.services.dca import (
    check_cell_access,
    create_dca_config,
    create_selective_access_grant,
    create_selective_access_rule,
    delete_dca_config,
    delete_selective_access_grant,
    get_dca_config,
    get_selective_access_grant,
    get_selective_access_rule,
    list_grants_for_rule,
    list_selective_access_rules,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["dca"])


# ---------------------------------------------------------------------------
# Selective Access Rules
# ---------------------------------------------------------------------------

@router.post(
    "/models/{model_id}/selective-access",
    response_model=SelectiveAccessRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    model_id: uuid.UUID,
    data: SelectiveAccessRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a selective access rule for a model."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if model.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    rule = await create_selective_access_rule(
        db, model_id, data.name, data.dimension_id, data.description
    )
    return SelectiveAccessRuleResponse.model_validate(rule)


@router.get(
    "/models/{model_id}/selective-access",
    response_model=List[SelectiveAccessRuleResponse],
)
async def list_rules(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all selective access rules for a model."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    rules = await list_selective_access_rules(db, model_id)
    return [SelectiveAccessRuleResponse.model_validate(r) for r in rules]


# ---------------------------------------------------------------------------
# Selective Access Grants
# ---------------------------------------------------------------------------

@router.post(
    "/selective-access/{rule_id}/grants",
    response_model=SelectiveAccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_grant(
    rule_id: uuid.UUID,
    data: SelectiveAccessGrantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a selective access grant to a rule."""
    rule = await get_selective_access_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    # Only model owner can manage grants
    model = await get_model_by_id(db, rule.model_id)
    if model is None or model.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    grant = await create_selective_access_grant(
        db, rule_id, data.user_id, data.dimension_item_id, data.access_level
    )
    return SelectiveAccessGrantResponse.model_validate(grant)


@router.get(
    "/selective-access/{rule_id}/grants",
    response_model=List[SelectiveAccessGrantResponse],
)
async def list_grants(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all grants for a rule."""
    rule = await get_selective_access_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    grants = await list_grants_for_rule(db, rule_id)
    return [SelectiveAccessGrantResponse.model_validate(g) for g in grants]


@router.delete(
    "/selective-access/{rule_id}/grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_grant(
    rule_id: uuid.UUID,
    grant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a selective access grant."""
    rule = await get_selective_access_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    model = await get_model_by_id(db, rule.model_id)
    if model is None or model.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    grant = await get_selective_access_grant(db, grant_id)
    if grant is None or grant.rule_id != rule_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

    deleted = await delete_selective_access_grant(db, grant_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")


# ---------------------------------------------------------------------------
# DCA Config
# ---------------------------------------------------------------------------

@router.post(
    "/line-items/{line_item_id}/dca",
    response_model=DCAConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_dca(
    line_item_id: uuid.UUID,
    data: DCAConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Configure DCA drivers for a line item."""
    config = await create_dca_config(
        db, line_item_id, data.read_driver_line_item_id, data.write_driver_line_item_id
    )
    return DCAConfigResponse.model_validate(config)


@router.get(
    "/line-items/{line_item_id}/dca",
    response_model=DCAConfigResponse,
)
async def get_dca(
    line_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get DCA configuration for a line item."""
    config = await get_dca_config(db, line_item_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DCA config not found")
    return DCAConfigResponse.model_validate(config)


@router.delete(
    "/line-items/{line_item_id}/dca",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_dca(
    line_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove DCA configuration for a line item."""
    deleted = await delete_dca_config(db, line_item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DCA config not found")


# ---------------------------------------------------------------------------
# Cell Access Check
# ---------------------------------------------------------------------------

@router.get(
    "/cells/access-check",
    response_model=CellAccessCheckResponse,
)
async def cell_access_check(
    line_item_id: uuid.UUID = Query(...),
    dimension_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check cell-level access for the current user."""
    result = await check_cell_access(db, current_user.id, line_item_id, dimension_key)
    return CellAccessCheckResponse(**result)
