import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SSOProviderCreate(BaseModel):
    workspace_id: uuid.UUID
    provider_type: str  # "saml" or "oidc"
    display_name: str
    issuer_url: str
    client_id: str
    client_secret: Optional[str] = None
    metadata_url: Optional[str] = None
    certificate: Optional[str] = None
    auto_provision: bool = True
    default_role: str = "viewer"
    domain_allowlist: Optional[List[str]] = None


class SSOProviderResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    provider_type: str
    display_name: str
    issuer_url: str
    client_id: str
    metadata_url: Optional[str]
    certificate: Optional[str]
    auto_provision: bool
    default_role: str
    domain_allowlist: Optional[List[str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SSOProviderUpdate(BaseModel):
    provider_type: Optional[str] = None
    display_name: Optional[str] = None
    issuer_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    metadata_url: Optional[str] = None
    certificate: Optional[str] = None
    auto_provision: Optional[bool] = None
    default_role: Optional[str] = None
    domain_allowlist: Optional[List[str]] = None
    is_active: Optional[bool] = None


class SSOLoginResponse(BaseModel):
    redirect_url: str
    state: str


class SSOCallbackRequest(BaseModel):
    code: str
    state: str


class SSOCallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    provisioned: bool = False


class SSOSessionValidateRequest(BaseModel):
    session_token: str


class SSOSessionResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
