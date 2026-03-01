import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class WorkspaceQuotaUpdate(BaseModel):
    max_models: Optional[int] = None
    max_cells_per_model: Optional[int] = None
    max_dimensions_per_model: Optional[int] = None
    storage_limit_mb: Optional[int] = None

    @field_validator(
        "max_models",
        "max_cells_per_model",
        "max_dimensions_per_model",
        "storage_limit_mb",
    )
    @classmethod
    def validate_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("Quota values must be greater than 0")
        return value


class WorkspaceQuotaResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    max_models: int
    max_cells_per_model: int
    max_dimensions_per_model: int
    storage_limit_mb: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelQuotaUsage(BaseModel):
    model_id: uuid.UUID
    model_name: str
    dimension_count: int
    cell_count: int
    storage_used_bytes: int
    storage_used_mb: float


class WorkspaceQuotaUsageResponse(BaseModel):
    workspace_id: uuid.UUID
    max_models: int
    max_cells_per_model: int
    max_dimensions_per_model: int
    storage_limit_mb: int
    model_count: int
    total_dimension_count: int
    total_cell_count: int
    storage_used_bytes: int
    storage_used_mb: float
    models: List[ModelQuotaUsage]
