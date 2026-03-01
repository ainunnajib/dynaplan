import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# SCIM Config schemas
# ---------------------------------------------------------------------------

class SCIMConfigCreate(BaseModel):
    bearer_token: str
    base_url: str = "http://localhost:8000"
    is_enabled: bool = True


class SCIMConfigUpdate(BaseModel):
    bearer_token: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None


class SCIMConfigResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    is_enabled: bool
    base_url: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# SCIM 2.0 User Resource
# ---------------------------------------------------------------------------

class SCIMUserName(BaseModel):
    formatted: Optional[str] = None
    familyName: Optional[str] = None
    givenName: Optional[str] = None


class SCIMUserEmail(BaseModel):
    value: str
    type: str = "work"
    primary: bool = True


class SCIMUserResource(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: Optional[str] = None
    externalId: Optional[str] = None
    userName: str
    name: Optional[SCIMUserName] = None
    emails: Optional[List[SCIMUserEmail]] = None
    active: bool = True
    displayName: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class SCIMUserCreate(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    externalId: Optional[str] = None
    userName: str
    name: Optional[SCIMUserName] = None
    emails: Optional[List[SCIMUserEmail]] = None
    active: bool = True
    displayName: Optional[str] = None
    password: Optional[str] = None


class SCIMPatchOp(BaseModel):
    op: str
    path: Optional[str] = None
    value: Optional[Any] = None


class SCIMPatchRequest(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    Operations: List[SCIMPatchOp]


# ---------------------------------------------------------------------------
# SCIM 2.0 Group Resource
# ---------------------------------------------------------------------------

class SCIMGroupMemberRef(BaseModel):
    value: str
    display: Optional[str] = None


class SCIMGroupResource(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    id: Optional[str] = None
    externalId: Optional[str] = None
    displayName: str
    members: Optional[List[SCIMGroupMemberRef]] = None
    meta: Optional[Dict[str, Any]] = None


class SCIMGroupCreate(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    externalId: Optional[str] = None
    displayName: str
    members: Optional[List[SCIMGroupMemberRef]] = None


# ---------------------------------------------------------------------------
# SCIM 2.0 List Response
# ---------------------------------------------------------------------------

class SCIMListResponse(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int
    itemsPerPage: int
    startIndex: int = 1
    Resources: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Provisioning Log
# ---------------------------------------------------------------------------

class SCIMProvisioningLogResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    operation: str
    resource_type: str
    resource_id: str
    external_id: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
