import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ── ListSubset schemas ────────────────────────────────────────────────────────

class ListSubsetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_dynamic: bool = False
    filter_expression: Optional[str] = None


class ListSubsetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_dynamic: Optional[bool] = None
    filter_expression: Optional[str] = None


class ListSubsetMemberResponse(BaseModel):
    id: uuid.UUID
    subset_id: uuid.UUID
    dimension_item_id: uuid.UUID

    model_config = {"from_attributes": True}


class ListSubsetResponse(BaseModel):
    id: uuid.UUID
    dimension_id: uuid.UUID
    name: str
    description: Optional[str]
    is_dynamic: bool
    filter_expression: Optional[str]
    created_at: datetime
    updated_at: datetime
    members: List[ListSubsetMemberResponse] = []

    model_config = {"from_attributes": True}


class ListSubsetSummaryResponse(BaseModel):
    """Response without members list, used in list endpoints."""
    id: uuid.UUID
    dimension_id: uuid.UUID
    name: str
    description: Optional[str]
    is_dynamic: bool
    filter_expression: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddMembersRequest(BaseModel):
    dimension_item_ids: List[uuid.UUID]


class ResolvedMemberItem(BaseModel):
    id: uuid.UUID
    name: str
    code: str

    model_config = {"from_attributes": True}


class ResolvedMembersResponse(BaseModel):
    subset_id: uuid.UUID
    subset_name: str
    is_dynamic: bool
    members: List[ResolvedMemberItem]


# ── LineItemSubset schemas ────────────────────────────────────────────────────

class LineItemSubsetCreate(BaseModel):
    name: str
    description: Optional[str] = None


class LineItemSubsetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class LineItemSubsetMemberResponse(BaseModel):
    id: uuid.UUID
    subset_id: uuid.UUID
    line_item_id: uuid.UUID

    model_config = {"from_attributes": True}


class LineItemSubsetResponse(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    members: List[LineItemSubsetMemberResponse] = []

    model_config = {"from_attributes": True}


class LineItemSubsetSummaryResponse(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddLineItemMembersRequest(BaseModel):
    line_item_ids: List[uuid.UUID]


class ResolvedLineItemMember(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class ResolvedLineItemMembersResponse(BaseModel):
    subset_id: uuid.UUID
    subset_name: str
    members: List[ResolvedLineItemMember]
