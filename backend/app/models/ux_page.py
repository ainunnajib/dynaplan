import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PageType(str, enum.Enum):
    board = "board"
    worksheet = "worksheet"
    report = "report"


class CardType(str, enum.Enum):
    grid = "grid"
    chart = "chart"
    button = "button"
    kpi = "kpi"
    text = "text"
    image = "image"
    filter = "filter"


class UXPage(Base):
    __tablename__ = "ux_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    parent_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("ux_pages.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    page_type: Mapped[PageType] = mapped_column(Enum(PageType), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    layout_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cards: Mapped[List["UXPageCard"]] = relationship(
        "UXPageCard",
        back_populates="page",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="UXPageCard.sort_order",
    )
    context_selectors: Mapped[List["UXContextSelector"]] = relationship(
        "UXContextSelector",
        back_populates="page",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="UXContextSelector.sort_order",
    )
    parent_page: Mapped[Optional["UXPage"]] = relationship(
        "UXPage",
        remote_side="UXPage.id",
        back_populates="child_pages",
        lazy="selectin",
    )
    child_pages: Mapped[List["UXPage"]] = relationship(
        "UXPage",
        back_populates="parent_page",
        lazy="selectin",
        order_by="UXPage.sort_order",
    )


class UXPageCard(Base):
    __tablename__ = "ux_page_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ux_pages.id", ondelete="CASCADE"), nullable=False
    )
    card_type: Mapped[CardType] = mapped_column(Enum(CardType), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    position_x: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    position_y: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    page: Mapped["UXPage"] = relationship("UXPage", back_populates="cards")


class UXContextSelector(Base):
    __tablename__ = "ux_context_selectors"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ux_pages.id", ondelete="CASCADE"), nullable=False
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dimensions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    allow_multi_select: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_member_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    page: Mapped["UXPage"] = relationship("UXPage", back_populates="context_selectors")
