import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccessLevel(str, enum.Enum):
    read = "read"
    write = "write"
    none = "none"


class SelectiveAccessRule(Base):
    __tablename__ = "selective_access_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    dimension: Mapped["Dimension"] = relationship("Dimension", lazy="selectin")  # noqa: F821
    grants: Mapped[list["SelectiveAccessGrant"]] = relationship(
        "SelectiveAccessGrant",
        back_populates="rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SelectiveAccessGrant(Base):
    __tablename__ = "selective_access_grants"
    __table_args__ = (
        UniqueConstraint("rule_id", "user_id", "dimension_item_id", name="uq_sa_grant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("selective_access_rules.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dimension_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimension_items.id", ondelete="CASCADE"), nullable=False
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        Enum(AccessLevel), nullable=False, default=AccessLevel.read
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rule: Mapped["SelectiveAccessRule"] = relationship(
        "SelectiveAccessRule", back_populates="grants", lazy="selectin"
    )
    user: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
    dimension_item: Mapped["DimensionItem"] = relationship("DimensionItem", lazy="selectin")  # noqa: F821


class DCAConfig(Base):
    __tablename__ = "dca_configs"
    __table_args__ = (
        UniqueConstraint("line_item_id", name="uq_dca_config_line_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    line_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("line_items.id", ondelete="CASCADE"), nullable=False
    )
    read_driver_line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("line_items.id", ondelete="SET NULL"), nullable=True
    )
    write_driver_line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("line_items.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    line_item: Mapped["LineItem"] = relationship(  # noqa: F821
        "LineItem", foreign_keys=[line_item_id], lazy="selectin"
    )
    read_driver: Mapped[Optional["LineItem"]] = relationship(  # noqa: F821
        "LineItem", foreign_keys=[read_driver_line_item_id], lazy="selectin"
    )
    write_driver: Mapped[Optional["LineItem"]] = relationship(  # noqa: F821
        "LineItem", foreign_keys=[write_driver_line_item_id], lazy="selectin"
    )
