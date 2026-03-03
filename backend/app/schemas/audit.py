import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.models.audit import AuditEventType


class AuditEntryResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    event_type: AuditEventType
    entity_type: str
    entity_id: str
    user_id: Optional[uuid.UUID]
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    metadata_: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogQuery(BaseModel):
    event_type: Optional[AuditEventType] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    after: Optional[datetime] = None
    before: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class AuditSummaryResponse(BaseModel):
    counts: Dict[str, int]
    total: int
