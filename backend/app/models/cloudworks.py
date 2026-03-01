import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ConnectorType(str, enum.Enum):
    s3 = "s3"
    gcs = "gcs"
    azure_blob = "azure_blob"
    sftp = "sftp"
    http = "http"
    database = "database"
    local_file = "local_file"


class ScheduleType(str, enum.Enum):
    import_ = "import"
    export = "export"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    retrying = "retrying"


class CloudWorksConnection(Base):
    __tablename__ = "cloudworks_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType), nullable=False
    )
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    creator: Mapped[Optional["User"]] = relationship("User", lazy="selectin")  # noqa: F821
    schedules: Mapped[list["CloudWorksSchedule"]] = relationship(
        "CloudWorksSchedule",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CloudWorksSchedule(Base):
    __tablename__ = "cloudworks_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cloudworks_connections.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schedule_type: Mapped[ScheduleType] = mapped_column(
        Enum(ScheduleType), nullable=False
    )
    cron_expression: Mapped[str] = mapped_column(String(255), nullable=False)
    source_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    target_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    connection: Mapped["CloudWorksConnection"] = relationship(
        "CloudWorksConnection", back_populates="schedules"
    )
    runs: Mapped[list["CloudWorksRun"]] = relationship(
        "CloudWorksRun",
        back_populates="schedule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CloudWorksRun(Base):
    __tablename__ = "cloudworks_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cloudworks_schedules.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), nullable=False, default=RunStatus.pending
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    records_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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

    schedule: Mapped["CloudWorksSchedule"] = relationship(
        "CloudWorksSchedule", back_populates="runs"
    )
