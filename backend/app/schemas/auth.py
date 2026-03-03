import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class UserRegister(BaseModel):
    email: str
    full_name: str
    password: str
    role: UserRole = UserRole.viewer


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: str


class PasswordReset(BaseModel):
    token: str
    new_password: str
