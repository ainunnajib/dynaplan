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


class StepType(str, enum.Enum):
    source = "source"
    transform = "transform"
    filter = "filter"
    map = "map"
    aggregate = "aggregate"
    publish = "publish"


class PipelineRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepLogStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    steps: Mapped[List["PipelineStep"]] = relationship(
        "PipelineStep",
        back_populates="pipeline",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PipelineStep.sort_order",
    )
    runs: Mapped[List["PipelineRun"]] = relationship(
        "PipelineRun",
        back_populates="pipeline",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PipelineRun.created_at.desc()",
    )


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[StepType] = mapped_column(
        Enum(StepType), nullable=False
    )
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pipeline: Mapped["Pipeline"] = relationship(
        "Pipeline", back_populates="steps", lazy="selectin"
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        Enum(PipelineRunStatus), default=PipelineRunStatus.pending, nullable=False
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_step_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("pipeline_steps.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pipeline: Mapped["Pipeline"] = relationship(
        "Pipeline", back_populates="runs", lazy="selectin"
    )
    triggerer: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
    error_step: Mapped[Optional["PipelineStep"]] = relationship(
        "PipelineStep", lazy="selectin", foreign_keys=[error_step_id]
    )
    step_logs: Mapped[List["PipelineStepLog"]] = relationship(
        "PipelineStepLog",
        back_populates="run",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PipelineStepLog.started_at",
    )


class PipelineStepLog(Base):
    __tablename__ = "pipeline_step_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pipeline_steps.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[StepLogStatus] = mapped_column(
        Enum(StepLogStatus), default=StepLogStatus.pending, nullable=False
    )
    records_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    records_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    log_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped["PipelineRun"] = relationship(
        "PipelineRun", back_populates="step_logs", lazy="selectin"
    )
    step: Mapped["PipelineStep"] = relationship(
        "PipelineStep", lazy="selectin"
    )
