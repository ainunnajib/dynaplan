import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class WorkspaceSecurityPolicyUpdate(BaseModel):
    ip_allowlist: Optional[List[str]] = None
    enforce_ip_allowlist: Optional[bool] = None
    require_client_certificate: Optional[bool] = None

    @field_validator("ip_allowlist")
    @classmethod
    def normalize_allowlist(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        normalized = []
        for entry in value:
            cleaned = entry.strip()
            if cleaned:
                normalized.append(cleaned)
        return normalized


class WorkspaceSecurityPolicyResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    ip_allowlist: Optional[List[str]]
    enforce_ip_allowlist: bool
    require_client_certificate: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceClientCertificateCreate(BaseModel):
    name: Optional[str] = None
    certificate_pem: Optional[str] = None
    fingerprint_sha256: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


class WorkspaceClientCertificateResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: Optional[str]
    fingerprint_sha256: str
    subject: Optional[str]
    issuer: Optional[str]
    serial_number: Optional[str]
    not_before: Optional[datetime]
    not_after: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
