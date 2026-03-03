from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    UniqueConstraint,
    Index,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.dimension import Dimension
    from app.models.saved_view import SavedView


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
    first = "first"
    last = "last"
    opening_balance = "opening_balance"
    closing_balance = "closing_balance"
    weighted_average = "weighted_average"
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
    conditional_format_rules: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    line_items: Mapped[List["LineItem"]] = relationship(
        "LineItem",
        back_populates="module",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    saved_views: Mapped[List["SavedView"]] = relationship(
        "SavedView",
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
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conditional_format_rules: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    module: Mapped["Module"] = relationship(
        "Module", back_populates="line_items", lazy="selectin"
    )
    line_item_dimensions: Mapped[List["LineItemDimension"]] = relationship(
        "LineItemDimension",
        back_populates="line_item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LineItemDimension.sort_order",
    )

    @property
    def applies_to_dimensions(self) -> List[uuid.UUID]:
        return [lid.dimension_id for lid in self.line_item_dimensions]


class LineItemDimension(Base):
    __tablename__ = "line_item_dimensions"
    __table_args__ = (
        UniqueConstraint(
            "line_item_id",
            "dimension_id",
            name="uq_line_item_dimensions_line_item_dimension",
        ),
        Index("ix_line_item_dimensions_dimension_id", "dimension_id"),
        Index("ix_line_item_dimensions_line_item_id", "line_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    line_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("line_items.id", ondelete="CASCADE"), nullable=False
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    line_item: Mapped["LineItem"] = relationship(
        "LineItem", back_populates="line_item_dimensions", lazy="selectin"
    )
    dimension: Mapped["Dimension"] = relationship(
        "Dimension", back_populates="line_item_dimensions", lazy="selectin"
    )
