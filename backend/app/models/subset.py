import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ListSubset(Base):
    __tablename__ = "list_subsets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filter_expression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list["ListSubsetMember"]] = relationship(
        "ListSubsetMember",
        back_populates="subset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ListSubsetMember(Base):
    __tablename__ = "list_subset_members"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    subset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("list_subsets.id", ondelete="CASCADE"), nullable=False
    )
    dimension_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimension_items.id", ondelete="CASCADE"), nullable=False
    )

    subset: Mapped["ListSubset"] = relationship(
        "ListSubset", back_populates="members", lazy="selectin"
    )


class LineItemSubset(Base):
    __tablename__ = "line_item_subsets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list["LineItemSubsetMember"]] = relationship(
        "LineItemSubsetMember",
        back_populates="subset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LineItemSubsetMember(Base):
    __tablename__ = "line_item_subset_members"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    subset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("line_item_subsets.id", ondelete="CASCADE"), nullable=False
    )
    line_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("line_items.id", ondelete="CASCADE"), nullable=False
    )

    subset: Mapped["LineItemSubset"] = relationship(
        "LineItemSubset", back_populates="members", lazy="selectin"
    )
