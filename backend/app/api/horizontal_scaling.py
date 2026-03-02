import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.horizontal_scaling import (
    HorizontalScalingStatusResponse,
    KubernetesManifestListResponse,
    ModelAssignmentResponse,
    ModelAssignmentUpdateRequest,
    ScalingCacheEntryResponse,
    ScalingCacheSetRequest,
    ScalingEventPublishRequest,
    ScalingEventResponse,
)
from app.services.horizontal_scaling import (
    horizontal_scaling_runtime,
    list_kubernetes_manifests,
)

router = APIRouter(tags=["horizontal-scaling"])


@router.get(
    "/observability/scaling/status",
    response_model=HorizontalScalingStatusResponse,
)
async def get_horizontal_scaling_status(
    current_user: User = Depends(get_current_user),
) -> HorizontalScalingStatusResponse:
    del current_user
    payload = await horizontal_scaling_runtime.get_status()
    return HorizontalScalingStatusResponse.model_validate(payload)


@router.get(
    "/observability/scaling/models/{model_id}/assignment",
    response_model=ModelAssignmentResponse,
)
async def get_model_assignment(
    model_id: uuid.UUID,
    auto_assign: bool = Query(default=True),
    ttl_seconds: int = Query(default=900, ge=1, le=86400),
    current_user: User = Depends(get_current_user),
) -> ModelAssignmentResponse:
    del current_user
    assignment = await horizontal_scaling_runtime.get_model_assignment(
        model_id=model_id,
        auto_assign=auto_assign,
        ttl_seconds=ttl_seconds,
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model assignment not found",
        )
    return ModelAssignmentResponse.model_validate(assignment)


@router.put(
    "/observability/scaling/models/{model_id}/assignment",
    response_model=ModelAssignmentResponse,
)
async def set_model_assignment(
    model_id: uuid.UUID,
    data: ModelAssignmentUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> ModelAssignmentResponse:
    del current_user
    assignment = await horizontal_scaling_runtime.assign_model(
        model_id=model_id,
        ttl_seconds=data.ttl_seconds,
        node_id=data.node_id,
        force=data.force,
    )
    return ModelAssignmentResponse.model_validate(assignment)


@router.put(
    "/observability/scaling/cache/{namespace}/{cache_key}",
    response_model=ScalingCacheEntryResponse,
)
async def set_cache_entry(
    namespace: str,
    cache_key: str,
    data: ScalingCacheSetRequest,
    current_user: User = Depends(get_current_user),
) -> ScalingCacheEntryResponse:
    del current_user
    result = await horizontal_scaling_runtime.set_cache_entry(
        namespace=namespace,
        cache_key=cache_key,
        value=data.value,
        ttl_seconds=data.ttl_seconds,
    )
    return ScalingCacheEntryResponse.model_validate(result)


@router.get(
    "/observability/scaling/cache/{namespace}/{cache_key}",
    response_model=ScalingCacheEntryResponse,
)
async def get_cache_entry(
    namespace: str,
    cache_key: str,
    current_user: User = Depends(get_current_user),
) -> ScalingCacheEntryResponse:
    del current_user
    result = await horizontal_scaling_runtime.get_cache_entry(
        namespace=namespace,
        cache_key=cache_key,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cache entry not found",
        )
    return ScalingCacheEntryResponse.model_validate(result)


@router.post(
    "/observability/scaling/events/{channel}",
    response_model=ScalingEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_event(
    channel: str,
    data: ScalingEventPublishRequest,
    current_user: User = Depends(get_current_user),
) -> ScalingEventResponse:
    del current_user
    result = await horizontal_scaling_runtime.publish_event(
        channel=channel,
        event_type=data.event_type,
        payload=data.payload,
    )
    return ScalingEventResponse.model_validate(result)


@router.get(
    "/observability/scaling/events/{channel}",
    response_model=List[ScalingEventResponse],
)
async def list_events(
    channel: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> List[ScalingEventResponse]:
    del current_user
    items = await horizontal_scaling_runtime.list_recent_events(
        channel=channel,
        limit=limit,
    )
    return [ScalingEventResponse.model_validate(item) for item in items]


@router.get(
    "/observability/scaling/kubernetes/manifests",
    response_model=KubernetesManifestListResponse,
)
async def get_kubernetes_manifests(
    current_user: User = Depends(get_current_user),
) -> KubernetesManifestListResponse:
    del current_user
    manifests = list_kubernetes_manifests()
    return KubernetesManifestListResponse(manifests=manifests)

