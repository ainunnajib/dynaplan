import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ModelEncryptionKey(Base):
    __tablename__ = "model_encryption_keys"
    __table_args__ = (
        UniqueConstraint("model_id", "key_version", name="uq_model_encryption_key_version"),
        Index("ix_model_encryption_keys_model_active", "model_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kms_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    kms_key_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    wrapped_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
