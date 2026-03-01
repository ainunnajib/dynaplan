import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.audit import AuditEventType
from app.models.user import User, UserRole
from app.schemas.audit import AuditEntryResponse, AuditSummaryResponse
from app.services.audit import (
    get_audit_log,
    get_audit_summary,
    get_entity_history,
    purge_old_entries,
)

router = APIRouter(tags=["audit"])


@router.get(
    "/models/{model_id}/audit",
    response_model=List[AuditEntryResponse],
)
async def get_model_audit_log(
    model_id: uuid.UUID,
    event_type: Optional[AuditEventType] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    user_id: Optional[uuid.UUID] = Query(default=None),
    after: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = await get_audit_log(
        db,
        model_id=model_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        after=after,
        before=before,
        limit=limit,
        offset=offset,
    )
    return entries


@router.get(
    "/models/{model_id}/audit/summary",
    response_model=AuditSummaryResponse,
)
async def get_model_audit_summary(
    model_id: uuid.UUID,
    after: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counts = await get_audit_summary(db, model_id=model_id, after=after, before=before)
    total = sum(counts.values())
    return AuditSummaryResponse(counts=counts, total=total)


@router.get(
    "/audit/entity/{entity_type}/{entity_id}",
    response_model=List[AuditEntryResponse],
)
async def get_audit_entity_history(
    entity_type: str,
    entity_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = await get_entity_history(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return entries


@router.delete(
    "/models/{model_id}/audit",
    status_code=status.HTTP_200_OK,
)
async def purge_model_audit_entries(
    model_id: uuid.UUID,
    before: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can purge audit entries",
        )
    deleted_count = await purge_old_entries(db, model_id=model_id, before_date=before)
    return {"deleted": deleted_count}
