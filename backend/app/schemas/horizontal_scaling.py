import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HorizontalScalingStatusResponse(BaseModel):
    node_id: str
    api_mode: str
    load_balancer_strategy: str
    state_backend: str
    redis_configured: bool
    redis_active: bool
    redis_error: Optional[str] = None
    model_assignments_tracked: int
    cache_entries_tracked: int
    event_channels_tracked: int


class ModelAssignmentUpdateRequest(BaseModel):
    node_id: Optional[str] = None
    ttl_seconds: int = Field(default=900, ge=1, le=86400)
    force: bool = False


class ModelAssignmentResponse(BaseModel):
    model_id: uuid.UUID
    node_id: str
    assigned_at: datetime
    expires_at: datetime
    backend: str


class ScalingCacheSetRequest(BaseModel):
    value: Any
    ttl_seconds: int = Field(default=300, ge=1, le=86400)


class ScalingCacheEntryResponse(BaseModel):
    namespace: str
    key: str
    value: Any
    updated_at: datetime
    expires_at: datetime
    backend: str


class ScalingEventPublishRequest(BaseModel):
    event_type: str = Field(default="message", min_length=1, max_length=128)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ScalingEventResponse(BaseModel):
    id: str
    channel: str
    event_type: str
    payload: Dict[str, Any]
    published_at: datetime
    node_id: str
    backend: str


class KubernetesManifestResponse(BaseModel):
    name: str
    content: str


class KubernetesManifestListResponse(BaseModel):
    manifests: List[KubernetesManifestResponse]

