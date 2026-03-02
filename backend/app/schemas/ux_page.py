import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.ux_page import CardType, PageType


# -- UXContextSelector schemas ------------------------------------------------

class UXContextSelectorCreate(BaseModel):
    dimension_id: uuid.UUID
    label: str
    allow_multi_select: bool = False
    default_member_id: Optional[uuid.UUID] = None
    sort_order: int = 0


class UXContextSelectorResponse(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    dimension_id: uuid.UUID
    label: str
    allow_multi_select: bool
    default_member_id: Optional[uuid.UUID]
    sort_order: int

    model_config = {"from_attributes": True}


# -- UXPageCard schemas -------------------------------------------------------

class UXPageCardCreate(BaseModel):
    card_type: CardType
    title: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    position_x: int = 0
    position_y: int = 0
    width: int = 6
    height: int = 4
    sort_order: int = 0


class UXPageCardUpdate(BaseModel):
    title: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sort_order: Optional[int] = None


class UXPageCardResponse(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    card_type: CardType
    title: Optional[str]
    config: Optional[Dict[str, Any]]
    position_x: int
    position_y: int
    width: int
    height: int
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# -- UXPage schemas -----------------------------------------------------------

class UXPageCreate(BaseModel):
    name: str
    page_type: PageType
    parent_page_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    layout_config: Optional[Dict[str, Any]] = None
    sort_order: int = 0


class UXPageUpdate(BaseModel):
    name: Optional[str] = None
    parent_page_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    layout_config: Optional[Dict[str, Any]] = None
    sort_order: Optional[int] = None


class UXPageResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    owner_id: uuid.UUID
    parent_page_id: Optional[uuid.UUID]
    name: str
    page_type: PageType
    description: Optional[str]
    layout_config: Optional[Dict[str, Any]]
    is_published: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UXPageDetailResponse(UXPageResponse):
    cards: List[UXPageCardResponse] = []
    context_selectors: List[UXContextSelectorResponse] = []


class UXPagePublishRequest(BaseModel):
    is_published: bool


class UXPageReorderRequest(BaseModel):
    page_ids: List[uuid.UUID]


class UXCardReorderRequest(BaseModel):
    card_ids: List[uuid.UUID]
