import enum
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProfileType(str, enum.Enum):
    classic = "classic"
    polaris = "polaris"


class GuidanceSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"


class EngineProfile(Base):
    __tablename__ = "engine_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("planning_models.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    profile_type: Mapped[ProfileType] = mapped_column(
        Enum(ProfileType), nullable=False
    )
    max_cells: Mapped[int] = mapped_column(BigInteger, nullable=False, default=10_000_000)
    max_dimensions: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_line_items: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    sparse_optimization: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    parallel_calc: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    memory_limit_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4096
    )
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    metrics: Mapped[List["EngineProfileMetric"]] = relationship(
        "EngineProfileMetric",
        back_populates="profile",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class EngineProfileMetric(Base):
    __tablename__ = "engine_profile_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("engine_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    profile: Mapped["EngineProfile"] = relationship(
        "EngineProfile", back_populates="metrics", lazy="selectin"
    )


class ModelDesignGuidance(Base):
    __tablename__ = "model_design_guidance"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    profile_type: Mapped[ProfileType] = mapped_column(
        Enum(ProfileType), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    severity: Mapped[GuidanceSeverity] = mapped_column(
        Enum(GuidanceSeverity), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
