import uuid
from typing import List, Optional

from pydantic import BaseModel

from app.models.rbac import ModelPermission, WorkspaceRole


class WorkspaceMemberCreate(BaseModel):
    user_email: str
    role: WorkspaceRole


class WorkspaceMemberUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: WorkspaceRole

    model_config = {"from_attributes": True}


class ModelAccessCreate(BaseModel):
    user_email: str
    permission: ModelPermission


class ModelAccessUpdate(BaseModel):
    permission: ModelPermission


class ModelAccessResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    permission: ModelPermission

    model_config = {"from_attributes": True}


class DimensionAccessCreate(BaseModel):
    dimension_id: uuid.UUID
    allowed_member_ids: List[str]


class DimensionAccessResponse(BaseModel):
    dimension_id: uuid.UUID
    allowed_member_ids: List[str]

    model_config = {"from_attributes": True}


class MyPermissionsResponse(BaseModel):
    workspace_role: Optional[WorkspaceRole] = None
    model_permission: Optional[ModelPermission] = None
