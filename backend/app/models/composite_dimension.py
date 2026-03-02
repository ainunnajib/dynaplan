import uuid
from datetime import datetime
from typing import List

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CompositeDimension(Base):
    __tablename__ = "composite_dimensions"
    __table_args__ = (
        UniqueConstraint("dimension_id", name="uq_composite_dimensions_dimension_id"),
        Index("ix_composite_dimensions_model_id", "model_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dimension: Mapped["Dimension"] = relationship(
        "Dimension", back_populates="composite_config", lazy="selectin"
    )
    source_dimensions: Mapped[List["CompositeDimensionSource"]] = relationship(
        "CompositeDimensionSource",
        back_populates="composite_dimension",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CompositeDimensionSource.sort_order",
    )
    members: Mapped[List["CompositeDimensionMember"]] = relationship(
        "CompositeDimensionMember",
        back_populates="composite_dimension",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CompositeDimensionSource(Base):
    __tablename__ = "composite_dimension_sources"
    __table_args__ = (
        UniqueConstraint(
            "composite_dimension_id",
            "source_dimension_id",
            name="uq_composite_dimension_sources_unique",
        ),
        Index(
            "ix_composite_dimension_sources_composite_dimension_id",
            "composite_dimension_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    composite_dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("composite_dimensions.id", ondelete="CASCADE"), nullable=False
    )
    source_dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    composite_dimension: Mapped["CompositeDimension"] = relationship(
        "CompositeDimension", back_populates="source_dimensions", lazy="selectin"
    )


class CompositeDimensionMember(Base):
    __tablename__ = "composite_dimension_members"
    __table_args__ = (
        UniqueConstraint(
            "composite_dimension_id",
            "source_member_key",
            name="uq_composite_dimension_members_source_key",
        ),
        UniqueConstraint(
            "dimension_item_id",
            name="uq_composite_dimension_members_dimension_item_id",
        ),
        Index(
            "ix_composite_dimension_members_composite_dimension_id",
            "composite_dimension_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    composite_dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("composite_dimensions.id", ondelete="CASCADE"), nullable=False
    )
    dimension_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimension_items.id", ondelete="CASCADE"), nullable=False
    )
    source_member_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    composite_dimension: Mapped["CompositeDimension"] = relationship(
        "CompositeDimension", back_populates="members", lazy="selectin"
    )
    dimension_item: Mapped["DimensionItem"] = relationship(
        "DimensionItem", lazy="selectin"
    )
