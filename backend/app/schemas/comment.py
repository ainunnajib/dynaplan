import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.comment import CommentTargetType


class CommentCreate(BaseModel):
    model_id: uuid.UUID
    target_type: CommentTargetType
    target_id: str
    content: str
    parent_id: Optional[uuid.UUID] = None


class CommentResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    target_type: CommentTargetType
    target_id: str
    content: str
    author_id: uuid.UUID
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    parent_id: Optional[uuid.UUID]
    is_resolved: bool
    resolved_by: Optional[uuid.UUID]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentResolve(BaseModel):
    resolved: bool


class MentionResponse(BaseModel):
    id: uuid.UUID
    comment_id: uuid.UUID
    mentioned_user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentWithMentionsResponse(CommentResponse):
    mention_user_ids: List[uuid.UUID] = []

    model_config = {"from_attributes": True}
