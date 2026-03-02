import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

from app.models.api_key import VALID_SCOPES


class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str]
    rate_limit_per_minute: Optional[int] = 120

    def validate_scopes(self) -> None:
        for scope in self.scopes:
            if scope not in VALID_SCOPES:
                raise ValueError(f"Invalid scope: {scope}. Valid scopes: {VALID_SCOPES}")

    @field_validator("rate_limit_per_minute")
    @classmethod
    def validate_rate_limit_per_minute(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value <= 0:
            raise ValueError("rate_limit_per_minute must be greater than 0")
        return value


class ApiKeyResponse(BaseModel):
    """Response schema — does NOT expose key_hash."""
    id: uuid.UUID
    name: str
    user_id: uuid.UUID
    scopes: List[str]
    is_active: bool
    rate_limit_per_minute: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only on creation — includes the raw key (shown once)."""
    raw_key: str
