import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.sso import (
    SSOCallbackRequest,
    SSOCallbackResponse,
    SSOLoginResponse,
    SSOProviderCreate,
    SSOProviderResponse,
    SSOProviderUpdate,
    SSOSessionResponse,
    SSOSessionValidateRequest,
)
from app.services.sso import (
    create_provider,
    delete_provider,
    get_provider_for_workspace,
    handle_sso_callback,
    initiate_sso_login,
    update_provider,
    validate_sso_session,
)
from app.services.workspace import get_workspace_by_id

router = APIRouter(tags=["sso"])


async def _require_workspace_owner(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dependency: verifies workspace exists and current user is the owner."""
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage SSO for this workspace",
        )
    return workspace


# ---------------------------------------------------------------------------
# Workspace-scoped SSO configuration endpoints (JWT protected)
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/sso",
    response_model=SSOProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sso_provider(
    workspace_id: uuid.UUID,
    data: SSOProviderCreate,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    # Enforce one provider per workspace
    existing = await get_provider_for_workspace(db, workspace_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An SSO provider already exists for this workspace",
        )
    provider = await create_provider(
        db=db,
        workspace_id=workspace_id,
        provider_type=data.provider_type,
        display_name=data.display_name,
        issuer_url=data.issuer_url,
        client_id=data.client_id,
        client_secret=data.client_secret,
        metadata_url=data.metadata_url,
        certificate=data.certificate,
        auto_provision=data.auto_provision,
        default_role=data.default_role,
        domain_allowlist=data.domain_allowlist,
    )
    return provider


@router.get("/workspaces/{workspace_id}/sso", response_model=SSOProviderResponse)
async def get_sso_provider(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    provider = await get_provider_for_workspace(db, workspace_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO provider configured for this workspace",
        )
    return provider


@router.patch("/workspaces/{workspace_id}/sso", response_model=SSOProviderResponse)
async def update_sso_provider(
    workspace_id: uuid.UUID,
    data: SSOProviderUpdate,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    provider = await get_provider_for_workspace(db, workspace_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO provider configured for this workspace",
        )
    updated = await update_provider(db, provider.id, **data.model_dump(exclude_none=True))
    return updated


@router.delete(
    "/workspaces/{workspace_id}/sso",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_sso_provider(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace=Depends(_require_workspace_owner),
):
    provider = await get_provider_for_workspace(db, workspace_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SSO provider configured for this workspace",
        )
    await delete_provider(db, provider.id)


# ---------------------------------------------------------------------------
# Public SSO flow endpoints (no JWT required)
# ---------------------------------------------------------------------------

@router.get("/sso/{workspace_id}/login", response_model=SSOLoginResponse)
async def initiate_login(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint: returns redirect URL to the identity provider."""
    result = await initiate_sso_login(db, workspace_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active SSO provider configured for this workspace",
        )
    return SSOLoginResponse(redirect_url=result["redirect_url"], state=result["state"])


@router.post("/sso/validate", response_model=SSOSessionResponse)
async def validate_session(
    data: SSOSessionValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint: validate an SSO session token."""
    session = await validate_sso_session(db, data.session_token)
    if session is None:
        return SSOSessionResponse(valid=False)
    return SSOSessionResponse(
        valid=True,
        user_id=str(session.user_id),
        email=session.user.email if session.user else None,
    )


@router.post("/sso/{workspace_id}/callback", response_model=SSOCallbackResponse)
async def sso_callback(
    workspace_id: uuid.UUID,
    data: SSOCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint: handle SSO callback and return a JWT."""
    provider = await get_provider_for_workspace(db, workspace_id)
    if provider is None or not provider.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active SSO provider configured for this workspace",
        )

    result = await handle_sso_callback(db, provider.id, data.code, data.state)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO callback processing failed",
        )
    if "error" in result:
        err_code = result["error"]
        if err_code == "domain_not_allowed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email domain is not allowed for this SSO provider",
            )
        if err_code == "user_not_provisioned":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Auto-provisioning is disabled; user must be pre-created",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO callback error",
        )

    return SSOCallbackResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        user_id=result["user_id"],
        email=result["email"],
        full_name=result["full_name"],
        provisioned=result["provisioned"],
    )
