import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ActionType(str, enum.Enum):
    import_data = "import_data"
    export_data = "export_data"
    delete_data = "delete_data"
    run_formula = "run_formula"
    copy_data = "copy_data"


class ProcessStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType), nullable=False
    )
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821


class Process(Base):
    __tablename__ = "processes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    steps: Mapped[list["ProcessStep"]] = relationship(
        "ProcessStep",
        back_populates="process",
        cascade="all, delete-orphan",
        order_by="ProcessStep.step_order",
        lazy="selectin",
    )


class ProcessStep(Base):
    __tablename__ = "process_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    process_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("actions.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    process: Mapped["Process"] = relationship("Process", back_populates="steps")
    action: Mapped["Action"] = relationship("Action", lazy="selectin")


class ProcessRun(Base):
    __tablename__ = "process_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    process_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("processes.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ProcessStatus] = mapped_column(
        Enum(ProcessStatus), nullable=False, default=ProcessStatus.pending
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    triggered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    process: Mapped["Process"] = relationship("Process", lazy="selectin")  # noqa: F821
    triggering_user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")  # noqa: F821
