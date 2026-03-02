import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class SavedViewSort(BaseModel):
    column_key: Optional[str] = None
    direction: str = "asc"

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"asc", "desc"}:
            raise ValueError("direction must be 'asc' or 'desc'")
        return normalized


class SavedViewConfig(BaseModel):
    row_dims: List[uuid.UUID] = Field(default_factory=list)
    col_dims: List[uuid.UUID] = Field(default_factory=list)
    filters: Dict[str, List[uuid.UUID]] = Field(default_factory=dict)
    sort: SavedViewSort = Field(default_factory=SavedViewSort)


class SavedViewCreate(BaseModel):
    name: str
    view_config: SavedViewConfig = Field(default_factory=SavedViewConfig)
    is_default: bool = False


class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    view_config: Optional[SavedViewConfig] = None
    is_default: Optional[bool] = None


class SavedViewResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    module_id: uuid.UUID
    name: str
    view_config: SavedViewConfig
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
