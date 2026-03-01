import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkspaceQuota(Base):
    __tablename__ = "workspace_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    max_models: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_cells_per_model: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1_000_000
    )
    max_dimensions_per_model: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200
    )
    storage_limit_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1024
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", lazy="selectin")  # noqa: F821
