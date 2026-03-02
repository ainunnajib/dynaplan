import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.workspace_security import (
    WorkspaceClientCertificateCreate,
    WorkspaceClientCertificateResponse,
    WorkspaceSecurityPolicyResponse,
    WorkspaceSecurityPolicyUpdate,
)
from app.services.workspace import get_workspace_by_id
from app.services.workspace_security import (
    WorkspaceClientCertificateExistsError,
    WorkspaceSecurityValidationError,
    deactivate_workspace_client_certificate,
    ensure_workspace_security_policy,
    get_workspace_client_certificate_by_id,
    list_workspace_client_certificates,
    register_workspace_client_certificate,
    update_workspace_security_policy,
)

router = APIRouter(tags=["workspace-security"])


async def _require_workspace_owner(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await get_workspace_by_id(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage workspace security",
        )
    return workspace


@router.get(
    "/workspaces/{workspace_id}/security",
    response_model=WorkspaceSecurityPolicyResponse,
)
async def get_workspace_security_policy_endpoint(
    workspace_id: uuid.UUID,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    del workspace
    return await ensure_workspace_security_policy(db, workspace_id)


@router.put(
    "/workspaces/{workspace_id}/security",
    response_model=WorkspaceSecurityPolicyResponse,
)
async def update_workspace_security_policy_endpoint(
    workspace_id: uuid.UUID,
    data: WorkspaceSecurityPolicyUpdate,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    del workspace
    policy = await ensure_workspace_security_policy(db, workspace_id)
    try:
        return await update_workspace_security_policy(
            db,
            policy,
            ip_allowlist=data.ip_allowlist,
            enforce_ip_allowlist=data.enforce_ip_allowlist,
            require_client_certificate=data.require_client_certificate,
        )
    except WorkspaceSecurityValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/workspaces/{workspace_id}/security/certificates",
    response_model=List[WorkspaceClientCertificateResponse],
)
async def list_workspace_security_certificates_endpoint(
    workspace_id: uuid.UUID,
    include_inactive: bool = Query(False),
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    del workspace
    certs = await list_workspace_client_certificates(
        db, workspace_id, include_inactive=include_inactive
    )
    return certs


@router.post(
    "/workspaces/{workspace_id}/security/certificates",
    response_model=WorkspaceClientCertificateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_workspace_security_certificate_endpoint(
    workspace_id: uuid.UUID,
    data: WorkspaceClientCertificateCreate,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    del workspace
    try:
        return await register_workspace_client_certificate(
            db,
            workspace_id,
            name=data.name,
            certificate_pem=data.certificate_pem,
            fingerprint_sha256=data.fingerprint_sha256,
        )
    except WorkspaceClientCertificateExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except WorkspaceSecurityValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/workspaces/{workspace_id}/security/certificates/{certificate_id}",
    response_model=WorkspaceClientCertificateResponse,
)
async def deactivate_workspace_security_certificate_endpoint(
    workspace_id: uuid.UUID,
    certificate_id: uuid.UUID,
    workspace=Depends(_require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    del workspace
    cert = await get_workspace_client_certificate_by_id(db, certificate_id)
    if cert is None or cert.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace client certificate not found",
        )
    return await deactivate_workspace_client_certificate(db, cert)
