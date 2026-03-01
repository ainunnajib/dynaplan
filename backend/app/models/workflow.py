import enum
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkflowStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    archived = "archived"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class ApprovalDecision(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.draft, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    creator: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
    stages: Mapped[List["WorkflowStage"]] = relationship(
        "WorkflowStage",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkflowStage.sort_order",
    )


class WorkflowStage(Base):
    __tablename__ = "workflow_stages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_gate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="stages", lazy="selectin"
    )
    tasks: Mapped[List["WorkflowTask"]] = relationship(
        "WorkflowTask",
        back_populates="stage",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending, nullable=False
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    stage: Mapped["WorkflowStage"] = relationship(
        "WorkflowStage", back_populates="tasks", lazy="selectin"
    )
    assignee: Mapped[Optional["User"]] = relationship("User", lazy="selectin")  # noqa: F821
    approvals: Mapped[List["WorkflowApproval"]] = relationship(
        "WorkflowApproval",
        back_populates="task",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class WorkflowApproval(Base):
    __tablename__ = "workflow_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(ApprovalDecision), nullable=False
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    task: Mapped["WorkflowTask"] = relationship(
        "WorkflowTask", back_populates="approvals", lazy="selectin"
    )
    approver: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
