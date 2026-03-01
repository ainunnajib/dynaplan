import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CommentTargetType(str, enum.Enum):
    cell = "cell"
    line_item = "line_item"
    module = "module"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[CommentTargetType] = mapped_column(
        Enum(CommentTargetType), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[author_id], lazy="selectin"
    )
    resolver: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[resolved_by], lazy="selectin"
    )
    mentions: Mapped[List["CommentMention"]] = relationship(
        "CommentMention", back_populates="comment", cascade="all, delete-orphan", lazy="selectin"
    )


class CommentMention(Base):
    __tablename__ = "comment_mentions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    comment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    mentioned_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    comment: Mapped["Comment"] = relationship("Comment", back_populates="mentions")
    mentioned_user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[mentioned_user_id], lazy="selectin"
    )
