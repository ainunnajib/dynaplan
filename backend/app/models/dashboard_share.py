import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SharePermission(str, enum.Enum):
    view = "view"
    edit = "edit"


class DashboardShare(Base):
    __tablename__ = "dashboard_shares"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "shared_with_user_id", name="uq_dashboard_share"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shared_with_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[SharePermission] = mapped_column(
        Enum(SharePermission), nullable=False, default=SharePermission.view
    )
    shared_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    dashboard: Mapped["Dashboard"] = relationship("Dashboard", lazy="selectin")  # noqa: F821
    shared_with_user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[shared_with_user_id], lazy="selectin"
    )
    shared_by_user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[shared_by_user_id], lazy="selectin"
    )


class DashboardContextFilter(Base):
    __tablename__ = "dashboard_context_filters"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False
    )
    selected_member_ids: Mapped[Optional[List]] = mapped_column(
        JSON, nullable=True, default=list
    )
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    dashboard: Mapped["Dashboard"] = relationship("Dashboard", lazy="selectin")  # noqa: F821
