import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TimeGranularity(str, enum.Enum):
    week = "week"
    month = "month"
    quarter = "quarter"
    half_year = "half_year"
    year = "year"


class WeekPattern(str, enum.Enum):
    iso = "iso"
    custom = "custom"


class RetailCalendarPattern(str, enum.Enum):
    standard = "standard"
    four_four_five = "4-4-5"
    four_five_four = "4-5-4"
    five_four_four = "5-4-4"


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
    fiscal_year_start_month: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    week_start_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    week_pattern: Mapped[WeekPattern] = mapped_column(
        Enum(WeekPattern), nullable=False, default=WeekPattern.iso
    )
    retail_pattern: Mapped[RetailCalendarPattern] = mapped_column(
        Enum(RetailCalendarPattern),
        nullable=False,
        default=RetailCalendarPattern.standard,
    )
    calendar_periods: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True, default=list
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
