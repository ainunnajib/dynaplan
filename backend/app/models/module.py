import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LineItemFormat(str, enum.Enum):
    number = "number"
    text = "text"
    boolean = "boolean"
    date = "date"
    list = "list"


class SummaryMethod(str, enum.Enum):
    sum = "sum"
    average = "average"
    min = "min"
    max = "max"
    none = "none"
    formula = "formula"


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    line_items: Mapped[List["LineItem"]] = relationship(
        "LineItem",
        back_populates="module",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[LineItemFormat] = mapped_column(
        Enum(LineItemFormat), nullable=False, default=LineItemFormat.number
    )
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_method: Mapped[SummaryMethod] = mapped_column(
        Enum(SummaryMethod), nullable=False, default=SummaryMethod.sum
    )
    applies_to_dimensions: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    module: Mapped["Module"] = relationship(
        "Module", back_populates="line_items", lazy="selectin"
    )
