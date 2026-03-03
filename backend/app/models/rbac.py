import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkspaceRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class ModelPermission(str, enum.Enum):
    full_access = "full_access"
    edit_data = "edit_data"
    view_only = "view_only"
    no_access = "no_access"


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[WorkspaceRole] = mapped_column(Enum(WorkspaceRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", lazy="selectin")  # noqa: F821
    user: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821


class ModelAccess(Base):
    __tablename__ = "model_access"
    __table_args__ = (UniqueConstraint("model_id", "user_id", name="uq_model_access"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[ModelPermission] = mapped_column(Enum(ModelPermission), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    user: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821


class DimensionMemberAccess(Base):
    __tablename__ = "dimension_member_access"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    allowed_member_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    user: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
