import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TimeGranularity(str, enum.Enum):
    month = "month"
    quarter = "quarter"
    year = "year"


class TimeRange(Base):
    __tablename__ = "time_ranges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_period: Mapped[str] = mapped_column(String(20), nullable=False)
    end_period: Mapped[str] = mapped_column(String(20), nullable=False)
    granularity: Mapped[TimeGranularity] = mapped_column(
        Enum(TimeGranularity), nullable=False, default=TimeGranularity.month
    )
    is_model_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ModuleTimeRange(Base):
    __tablename__ = "module_time_ranges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    time_range_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("time_ranges.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
