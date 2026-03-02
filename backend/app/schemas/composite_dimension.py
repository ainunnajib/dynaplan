import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.models.dimension import DimensionType


class CompositeDimensionCreate(BaseModel):
    name: str
    source_dimension_ids: List[uuid.UUID]


class CompositeDimensionResponse(BaseModel):
    id: uuid.UUID
    dimension_id: uuid.UUID
    model_id: uuid.UUID
    name: str
    dimension_type: DimensionType
    source_dimension_ids: List[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class CompositeIntersectionCreate(BaseModel):
    source_member_ids: List[uuid.UUID]


class CompositeIntersectionResponse(BaseModel):
    id: uuid.UUID
    dimension_item_id: uuid.UUID
    composite_dimension_id: uuid.UUID
    source_member_ids: List[uuid.UUID]
    name: str
    code: str
    sort_order: int
    created_at: datetime
    updated_at: datetime
