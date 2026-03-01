import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.version import VersionType


# ── Version schemas ────────────────────────────────────────────────────────────

class VersionCreate(BaseModel):
    name: str
    version_type: VersionType = VersionType.forecast
    is_default: bool = False
    switchover_period: Optional[str] = None


class VersionUpdate(BaseModel):
    name: Optional[str] = None
    version_type: Optional[VersionType] = None
    is_default: Optional[bool] = None
    switchover_period: Optional[str] = None


class VersionResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_id: uuid.UUID
    version_type: VersionType
    is_default: bool
    switchover_period: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Version comparison schemas ─────────────────────────────────────────────────

class VersionCompareRequest(BaseModel):
    version_id_a: uuid.UUID
    version_id_b: uuid.UUID
    line_item_id: uuid.UUID


class CellVariance(BaseModel):
    """Variance between two version cells for a single dimension key."""
    dimension_key: str
    value_a: Optional[float]
    value_b: Optional[float]
    variance_absolute: Optional[float]
    variance_percentage: Optional[float]


class VersionCompareResponse(BaseModel):
    version_id_a: uuid.UUID
    version_id_b: uuid.UUID
    version_name_a: str
    version_name_b: str
    line_item_id: uuid.UUID
    cells: List[CellVariance]
