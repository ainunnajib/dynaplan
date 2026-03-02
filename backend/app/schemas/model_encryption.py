import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

SUPPORTED_KMS_PROVIDERS = {"local", "aws_kms", "vault"}


class ModelEncryptionEnableRequest(BaseModel):
    kms_provider: str = "local"
    kms_key_id: Optional[str] = None

    @field_validator("kms_provider")
    @classmethod
    def validate_kms_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_KMS_PROVIDERS:
            raise ValueError("kms_provider must be one of: local, aws_kms, vault")
        return normalized


class ModelEncryptionRotateRequest(BaseModel):
    kms_provider: Optional[str] = None
    kms_key_id: Optional[str] = None

    @field_validator("kms_provider")
    @classmethod
    def validate_kms_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_KMS_PROVIDERS:
            raise ValueError("kms_provider must be one of: local, aws_kms, vault")
        return normalized


class ModelEncryptionStatusResponse(BaseModel):
    model_id: uuid.UUID
    encryption_enabled: bool
    active_key_version: Optional[int]
    kms_provider: Optional[str]
    kms_key_id: Optional[str]
    key_count: int
    rotated_at: Optional[datetime]


class ModelEncryptionKeyResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    key_version: int
    kms_provider: str
    kms_key_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
