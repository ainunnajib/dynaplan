import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Request schemas ─────────────────────────────────────────────────────────────

class SnapshotCreate(BaseModel):
    name: str
    description: Optional[str] = None


class SnapshotCompareRequest(BaseModel):
    snapshot_a_id: uuid.UUID
    snapshot_b_id: uuid.UUID


# ── Response schemas ────────────────────────────────────────────────────────────

class SnapshotMetadataResponse(BaseModel):
    """Snapshot metadata without the large data field."""
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    description: Optional[str]
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotDetailResponse(BaseModel):
    """Full snapshot including serialized model data."""
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    description: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
    snapshot_data: Optional[Dict[str, Any]]

    model_config = {"from_attributes": True}


# ── Restore & compare schemas ───────────────────────────────────────────────────

class RestoreResult(BaseModel):
    """Summary of entities restored from a snapshot."""
    snapshot_id: uuid.UUID
    model_id: uuid.UUID
    entities_restored: Dict[str, int]


class EntityDiff(BaseModel):
    """Diff counts for a single entity type."""
    added: int = 0
    removed: int = 0
    changed: int = 0


class SnapshotComparison(BaseModel):
    """Comparison result between two snapshots."""
    snapshot_id_a: uuid.UUID
    snapshot_id_b: uuid.UUID
    snapshot_name_a: str
    snapshot_name_b: str
    dimensions: EntityDiff
    dimension_items: EntityDiff
    modules: EntityDiff
    line_items: EntityDiff
    cell_values: EntityDiff
    versions: EntityDiff
    summary: str
