import ipaddress
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Process
from app.models.api_key import ApiKey
from app.models.dimension import Dimension
from app.models.module import LineItem, Module
from app.models.pipeline import Pipeline, PipelineRun
from app.models.planning_model import PlanningModel
from app.models.workspace_security import (
    WorkspaceClientCertificate,
    WorkspaceSecurityPolicy,
)

DEFAULT_API_KEY_RATE_LIMIT_PER_MINUTE = 120

_RATE_LIMIT_STATE: Dict[uuid.UUID, Tuple[int, int]] = {}
_RATE_LIMIT_LOCK = threading.Lock()


class WorkspaceSecurityError(ValueError):
    """Base workspace security error."""


class WorkspaceSecurityValidationError(WorkspaceSecurityError):
    """Raised when workspace security settings are invalid."""


class WorkspaceIPAddressNotAllowedError(WorkspaceSecurityError):
    """Raised when a request IP is not in workspace allowlist."""


class WorkspaceClientCertificateExistsError(WorkspaceSecurityError):
    """Raised when a certificate fingerprint is already registered."""


class WorkspaceClientCertificateAuthError(WorkspaceSecurityError):
    """Raised when certificate-based authentication fails."""


class ApiKeyRateLimitExceededError(WorkspaceSecurityError):
    """Raised when an API key exceeds request rate limits."""

    def __init__(self, limit: int, retry_after_seconds: int):
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            "API key rate limit exceeded (%s requests/minute)" % limit
        )


def reset_api_key_rate_limit_cache() -> None:
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_STATE.clear()


def _normalize_fingerprint(fingerprint: str) -> str:
    cleaned = (
        fingerprint.strip().lower().replace(":", "").replace(" ", "")
    )
    if len(cleaned) != 64:
        raise WorkspaceSecurityValidationError(
            "Certificate fingerprint must be a 64-character SHA-256 hex string"
        )
    if not all(ch in "0123456789abcdef" for ch in cleaned):
        raise WorkspaceSecurityValidationError(
            "Certificate fingerprint must be a valid SHA-256 hex string"
        )
    return cleaned


def _normalize_ip_allowlist(
    ip_allowlist: Optional[List[str]],
) -> Optional[List[str]]:
    if ip_allowlist is None:
        return None

    normalized: List[str] = []
    seen: Set[str] = set()
    for entry in ip_allowlist:
        candidate = entry.strip()
        if not candidate:
            continue
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError as exc:
            raise WorkspaceSecurityValidationError(
                "Invalid IP allowlist entry: '%s'" % entry
            ) from exc
        as_text = str(network)
        if as_text in seen:
            continue
        seen.add(as_text)
        normalized.append(as_text)
    return normalized


def _normalize_cert_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _decode_certificate_header_value(raw_value: str) -> str:
    decoded = unquote(raw_value).strip()
    decoded = decoded.replace("\\n", "\n")
    return decoded


def _parse_certificate_pem(
    certificate_pem: str,
) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[datetime], Optional[datetime]]:
    cleaned = _decode_certificate_header_value(certificate_pem)
    if "-----BEGIN CERTIFICATE-----" not in cleaned:
        raise WorkspaceSecurityValidationError(
            "certificate_pem must contain a valid PEM certificate"
        )

    try:
        cert = x509.load_pem_x509_certificate(cleaned.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise WorkspaceSecurityValidationError(
            "Failed to parse client certificate PEM"
        ) from exc

    fingerprint = cert.fingerprint(hashes.SHA256()).hex()
    subject = cert.subject.rfc4514_string() if cert.subject else None
    issuer = cert.issuer.rfc4514_string() if cert.issuer else None
    serial_number = format(cert.serial_number, "x")

    not_before = getattr(cert, "not_valid_before_utc", None)
    not_after = getattr(cert, "not_valid_after_utc", None)
    if not_before is None:
        not_before = _normalize_cert_datetime(cert.not_valid_before)
    if not_after is None:
        not_after = _normalize_cert_datetime(cert.not_valid_after)

    return fingerprint, subject, issuer, serial_number, not_before, not_after


def extract_client_ip_from_request(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    candidate = None
    if forwarded:
        candidate = forwarded.split(",")[0].strip()

    if not candidate:
        candidate = request.headers.get("X-Real-IP")

    if not candidate and request.client is not None:
        candidate = request.client.host

    if not candidate:
        return None

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def extract_client_certificate_fingerprint(request: Request) -> Optional[str]:
    fingerprint_header = request.headers.get("X-Client-Cert-Fingerprint")
    if fingerprint_header:
        return _normalize_fingerprint(fingerprint_header)

    cert_header = request.headers.get("X-Client-Cert")
    if not cert_header:
        return None

    fingerprint, _subject, _issuer, _serial, _nb, _na = _parse_certificate_pem(
        cert_header
    )
    return _normalize_fingerprint(fingerprint)


def enforce_api_key_rate_limit(api_key: ApiKey) -> None:
    limit = int(
        api_key.rate_limit_per_minute
        if api_key.rate_limit_per_minute is not None
        else DEFAULT_API_KEY_RATE_LIMIT_PER_MINUTE
    )
    if limit <= 0:
        return

    now_seconds = int(time.time())
    current_bucket = now_seconds // 60

    with _RATE_LIMIT_LOCK:
        bucket, count = _RATE_LIMIT_STATE.get(api_key.id, (current_bucket, 0))
        if bucket != current_bucket:
            bucket = current_bucket
            count = 0

        if count >= limit:
            retry_after_seconds = ((bucket + 1) * 60) - now_seconds
            if retry_after_seconds <= 0:
                retry_after_seconds = 1
            raise ApiKeyRateLimitExceededError(
                limit=limit, retry_after_seconds=retry_after_seconds
            )

        _RATE_LIMIT_STATE[api_key.id] = (bucket, count + 1)


async def get_workspace_security_policy(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> Optional[WorkspaceSecurityPolicy]:
    result = await db.execute(
        select(WorkspaceSecurityPolicy).where(
            WorkspaceSecurityPolicy.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()


async def create_default_workspace_security_policy(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspaceSecurityPolicy:
    policy = WorkspaceSecurityPolicy(
        workspace_id=workspace_id,
        ip_allowlist=None,
        enforce_ip_allowlist=False,
        require_client_certificate=False,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


async def ensure_workspace_security_policy(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> WorkspaceSecurityPolicy:
    existing = await get_workspace_security_policy(db, workspace_id)
    if existing is not None:
        return existing
    return await create_default_workspace_security_policy(db, workspace_id)


async def update_workspace_security_policy(
    db: AsyncSession,
    policy: WorkspaceSecurityPolicy,
    *,
    ip_allowlist: Optional[List[str]] = None,
    enforce_ip_allowlist: Optional[bool] = None,
    require_client_certificate: Optional[bool] = None,
) -> WorkspaceSecurityPolicy:
    next_allowlist = (
        _normalize_ip_allowlist(ip_allowlist)
        if ip_allowlist is not None
        else policy.ip_allowlist
    )
    next_enforce_ip_allowlist = (
        enforce_ip_allowlist
        if enforce_ip_allowlist is not None
        else policy.enforce_ip_allowlist
    )
    next_require_client_certificate = (
        require_client_certificate
        if require_client_certificate is not None
        else policy.require_client_certificate
    )

    if next_enforce_ip_allowlist and not next_allowlist:
        raise WorkspaceSecurityValidationError(
            "ip_allowlist cannot be empty when enforce_ip_allowlist is enabled"
        )

    policy.ip_allowlist = next_allowlist
    policy.enforce_ip_allowlist = bool(next_enforce_ip_allowlist)
    policy.require_client_certificate = bool(next_require_client_certificate)
    await db.commit()
    await db.refresh(policy)
    return policy


async def list_workspace_client_certificates(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    include_inactive: bool = False,
) -> List[WorkspaceClientCertificate]:
    stmt = (
        select(WorkspaceClientCertificate)
        .where(WorkspaceClientCertificate.workspace_id == workspace_id)
        .order_by(WorkspaceClientCertificate.created_at.asc())
    )
    if not include_inactive:
        stmt = stmt.where(WorkspaceClientCertificate.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_workspace_client_certificate_by_id(
    db: AsyncSession,
    certificate_id: uuid.UUID,
) -> Optional[WorkspaceClientCertificate]:
    result = await db.execute(
        select(WorkspaceClientCertificate).where(
            WorkspaceClientCertificate.id == certificate_id
        )
    )
    return result.scalar_one_or_none()


async def get_active_workspace_certificate_by_fingerprint(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    fingerprint_sha256: str,
) -> Optional[WorkspaceClientCertificate]:
    result = await db.execute(
        select(WorkspaceClientCertificate).where(
            WorkspaceClientCertificate.workspace_id == workspace_id,
            WorkspaceClientCertificate.fingerprint_sha256
            == _normalize_fingerprint(fingerprint_sha256),
            WorkspaceClientCertificate.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def register_workspace_client_certificate(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    name: Optional[str] = None,
    certificate_pem: Optional[str] = None,
    fingerprint_sha256: Optional[str] = None,
) -> WorkspaceClientCertificate:
    if not certificate_pem and not fingerprint_sha256:
        raise WorkspaceSecurityValidationError(
            "Either certificate_pem or fingerprint_sha256 is required"
        )

    parsed_fingerprint: Optional[str] = None
    subject: Optional[str] = None
    issuer: Optional[str] = None
    serial_number: Optional[str] = None
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None

    if certificate_pem:
        (
            parsed_fingerprint,
            subject,
            issuer,
            serial_number,
            not_before,
            not_after,
        ) = _parse_certificate_pem(certificate_pem)

    normalized_input_fingerprint = (
        _normalize_fingerprint(fingerprint_sha256)
        if fingerprint_sha256
        else None
    )
    normalized_parsed_fingerprint = (
        _normalize_fingerprint(parsed_fingerprint)
        if parsed_fingerprint
        else None
    )

    if normalized_input_fingerprint and normalized_parsed_fingerprint:
        if normalized_input_fingerprint != normalized_parsed_fingerprint:
            raise WorkspaceSecurityValidationError(
                "fingerprint_sha256 does not match certificate_pem fingerprint"
            )

    final_fingerprint = normalized_input_fingerprint or normalized_parsed_fingerprint
    if final_fingerprint is None:
        raise WorkspaceSecurityValidationError(
            "Unable to resolve certificate fingerprint"
        )

    result = await db.execute(
        select(WorkspaceClientCertificate).where(
            WorkspaceClientCertificate.workspace_id == workspace_id,
            WorkspaceClientCertificate.fingerprint_sha256 == final_fingerprint,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None and existing.is_active:
        raise WorkspaceClientCertificateExistsError(
            "Certificate fingerprint is already registered for this workspace"
        )

    if existing is not None:
        existing.name = name
        existing.subject = subject
        existing.issuer = issuer
        existing.serial_number = serial_number
        existing.not_before = not_before
        existing.not_after = not_after
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    cert = WorkspaceClientCertificate(
        workspace_id=workspace_id,
        name=name,
        fingerprint_sha256=final_fingerprint,
        subject=subject,
        issuer=issuer,
        serial_number=serial_number,
        not_before=not_before,
        not_after=not_after,
        is_active=True,
    )
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


async def deactivate_workspace_client_certificate(
    db: AsyncSession,
    certificate: WorkspaceClientCertificate,
) -> WorkspaceClientCertificate:
    certificate.is_active = False
    await db.commit()
    await db.refresh(certificate)
    return certificate


def _is_ip_allowed(client_ip: str, allowlist: List[str]) -> bool:
    try:
        ip_value = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for allowlist_entry in allowlist:
        try:
            network = ipaddress.ip_network(allowlist_entry, strict=False)
        except ValueError:
            continue
        if ip_value in network:
            return True
    return False


async def enforce_workspace_request_security(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    request: Request,
) -> None:
    policy = await ensure_workspace_security_policy(db, workspace_id)

    if policy.enforce_ip_allowlist:
        allowlist = policy.ip_allowlist or []
        if len(allowlist) == 0:
            raise WorkspaceIPAddressNotAllowedError(
                "Workspace IP allowlist is enabled but empty"
            )
        client_ip = extract_client_ip_from_request(request)
        if client_ip is None:
            raise WorkspaceIPAddressNotAllowedError(
                "Unable to determine client IP address"
            )
        if not _is_ip_allowed(client_ip, allowlist):
            raise WorkspaceIPAddressNotAllowedError(
                "IP address is not in the workspace allowlist"
            )

    if policy.require_client_certificate:
        fingerprint = extract_client_certificate_fingerprint(request)
        if fingerprint is None:
            raise WorkspaceClientCertificateAuthError(
                "Client certificate is required for this workspace"
            )
        cert = await get_active_workspace_certificate_by_fingerprint(
            db, workspace_id, fingerprint
        )
        if cert is None:
            raise WorkspaceClientCertificateAuthError(
                "Client certificate is not allowlisted for this workspace"
            )


async def resolve_workspace_id_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id).where(PlanningModel.id == model_id)
    )
    return result.scalar_one_or_none()


async def resolve_workspace_id_for_dimension(
    db: AsyncSession,
    dimension_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(Dimension)
        .join(PlanningModel, PlanningModel.id == Dimension.model_id)
        .where(Dimension.id == dimension_id)
    )
    return result.scalar_one_or_none()


async def resolve_workspace_id_for_module(
    db: AsyncSession,
    module_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(Module)
        .join(PlanningModel, PlanningModel.id == Module.model_id)
        .where(Module.id == module_id)
    )
    return result.scalar_one_or_none()


async def resolve_workspace_id_for_line_item(
    db: AsyncSession,
    line_item_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(LineItem)
        .join(Module, Module.id == LineItem.module_id)
        .join(PlanningModel, PlanningModel.id == Module.model_id)
        .where(LineItem.id == line_item_id)
    )
    return result.scalar_one_or_none()


async def resolve_workspace_ids_for_line_items(
    db: AsyncSession,
    line_item_ids: List[uuid.UUID],
) -> List[uuid.UUID]:
    if len(line_item_ids) == 0:
        return []

    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(LineItem)
        .join(Module, Module.id == LineItem.module_id)
        .join(PlanningModel, PlanningModel.id == Module.model_id)
        .where(LineItem.id.in_(line_item_ids))
    )
    workspace_ids = list(result.scalars().all())
    deduped: List[uuid.UUID] = []
    seen: Set[uuid.UUID] = set()
    for workspace_id in workspace_ids:
        if workspace_id in seen:
            continue
        seen.add(workspace_id)
        deduped.append(workspace_id)
    return deduped


async def resolve_workspace_id_for_process(
    db: AsyncSession,
    process_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(Process)
        .join(PlanningModel, PlanningModel.id == Process.model_id)
        .where(Process.id == process_id)
    )
    return result.scalar_one_or_none()


async def resolve_workspace_id_for_pipeline(
    db: AsyncSession,
    pipeline_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(Pipeline)
        .join(PlanningModel, PlanningModel.id == Pipeline.model_id)
        .where(Pipeline.id == pipeline_id)
    )
    return result.scalar_one_or_none()


async def resolve_workspace_id_for_pipeline_run(
    db: AsyncSession,
    run_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(PlanningModel.workspace_id)
        .select_from(PipelineRun)
        .join(Pipeline, Pipeline.id == PipelineRun.pipeline_id)
        .join(PlanningModel, PlanningModel.id == Pipeline.model_id)
        .where(PipelineRun.id == run_id)
    )
    return result.scalar_one_or_none()
