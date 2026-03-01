import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CellValue(Base):
    __tablename__ = "cell_values"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    line_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("line_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Sorted, pipe-separated string of dimension_item UUIDs e.g. "uuid1|uuid2|uuid3"
    dimension_key: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )
    value_number: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_boolean: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("line_item_id", "dimension_key", name="uq_cell_line_item_dimension"),
        Index("ix_cell_line_item_dimension", "line_item_id", "dimension_key"),
    )
