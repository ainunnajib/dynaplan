import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CalcCache(Base):
    __tablename__ = "calc_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    line_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    dimension_key: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    computed_value: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    # SHA-256 of the formula used to compute this value
    formula_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("line_item_id", "dimension_key", name="uq_calc_cache_line_item_dimension"),
        Index("ix_calc_cache_model_valid", "model_id", "is_valid"),
    )
