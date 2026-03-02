import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# ALMEnvironment
# ---------------------------------------------------------------------------


class EnvironmentCreate(BaseModel):
    env_type: str  # "dev", "test", "prod"
    name: str
    description: Optional[str] = None
    source_env_id: Optional[uuid.UUID] = None


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class EnvironmentResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    env_type: str
    name: str
    description: Optional[str]
    source_env_id: Optional[uuid.UUID]
    is_locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LockRequest(BaseModel):
    is_locked: bool


# ---------------------------------------------------------------------------
# RevisionTag
# ---------------------------------------------------------------------------


class RevisionTagCreate(BaseModel):
    tag_name: str
    description: Optional[str] = None
    snapshot_data: Optional[dict] = None


class RevisionTagResponse(BaseModel):
    id: uuid.UUID
    environment_id: uuid.UUID
    tag_name: str
    description: Optional[str]
    created_by: uuid.UUID
    snapshot_data: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# PromotionRecord
# ---------------------------------------------------------------------------


class PromotionCreate(BaseModel):
    target_env_id: uuid.UUID
    revision_tag_id: uuid.UUID
    merge_strategy: Literal["additive", "replace", "manual"] = "additive"
    change_summary: Optional[dict] = None


class PromotionResponse(BaseModel):
    id: uuid.UUID
    source_env_id: uuid.UUID
    target_env_id: uuid.UUID
    revision_tag_id: uuid.UUID
    promoted_by: uuid.UUID
    status: str
    change_summary: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Tag comparison
# ---------------------------------------------------------------------------


class TagComparisonResponse(BaseModel):
    tag_1_id: uuid.UUID
    tag_1_name: str
    tag_2_id: uuid.UUID
    tag_2_name: str
    added: Dict
    removed: Dict
    modified: Dict
