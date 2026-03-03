import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.dca import AccessLevel


# ---------------------------------------------------------------------------
# Selective Access Rule
# ---------------------------------------------------------------------------

class SelectiveAccessRuleCreate(BaseModel):
    name: str
    dimension_id: uuid.UUID
    description: Optional[str] = None


class SelectiveAccessRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SelectiveAccessRuleResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    dimension_id: uuid.UUID
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Selective Access Grant
# ---------------------------------------------------------------------------

class SelectiveAccessGrantCreate(BaseModel):
    user_id: uuid.UUID
    dimension_item_id: uuid.UUID
    access_level: AccessLevel = AccessLevel.read


class SelectiveAccessGrantResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    user_id: uuid.UUID
    dimension_item_id: uuid.UUID
    access_level: AccessLevel
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# DCA Config
# ---------------------------------------------------------------------------

class DCAConfigCreate(BaseModel):
    read_driver_line_item_id: Optional[uuid.UUID] = None
    write_driver_line_item_id: Optional[uuid.UUID] = None


class DCAConfigUpdate(BaseModel):
    read_driver_line_item_id: Optional[uuid.UUID] = None
    write_driver_line_item_id: Optional[uuid.UUID] = None


class DCAConfigResponse(BaseModel):
    id: uuid.UUID
    line_item_id: uuid.UUID
    read_driver_line_item_id: Optional[uuid.UUID] = None
    write_driver_line_item_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Cell Access Check
# ---------------------------------------------------------------------------

class CellAccessCheckResponse(BaseModel):
    can_read: bool
    can_write: bool
    reason: str
