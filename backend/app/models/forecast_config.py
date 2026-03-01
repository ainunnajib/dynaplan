import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ForecastConfig(Base):
    __tablename__ = "forecast_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    forecast_horizon_months: Mapped[int] = mapped_column(
        Integer, nullable=False, default=12
    )
    auto_archive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    archive_actuals_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True
    )
    forecast_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True
    )
    last_rolled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("model_id", name="uq_forecast_config_model"),
    )
