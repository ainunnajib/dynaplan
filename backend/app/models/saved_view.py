import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SavedView(Base):
    __tablename__ = "saved_views"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "module_id",
            "name",
            name="uq_saved_views_user_module_name",
        ),
        Index("ix_saved_views_module_id", "module_id"),
        Index("ix_saved_views_user_id", "user_id"),
        Index(
            "ix_saved_views_user_module_default",
            "user_id",
            "module_id",
            "is_default",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    view_config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    module: Mapped["Module"] = relationship(
        "Module", back_populates="saved_views", lazy="selectin"
    )
    user: Mapped["User"] = relationship("User", lazy="selectin")
