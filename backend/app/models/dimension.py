import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DimensionType(str, enum.Enum):
    custom = "custom"
    time = "time"
    version = "version"
    numbered = "numbered"


class Dimension(Base):
    __tablename__ = "dimensions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension_type: Mapped[DimensionType] = mapped_column(
        Enum(DimensionType), nullable=False, default=DimensionType.custom
    )
    max_items: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[List["DimensionItem"]] = relationship(
        "DimensionItem",
        back_populates="dimension",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DimensionItem(Base):
    __tablename__ = "dimension_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("dimension_items.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dimension: Mapped["Dimension"] = relationship(
        "Dimension", back_populates="items", lazy="selectin"
    )
