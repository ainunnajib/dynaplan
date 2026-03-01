import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EnvironmentType(str, enum.Enum):
    dev = "dev"
    test = "test"
    prod = "prod"


class PromotionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    rolled_back = "rolled_back"


class ALMEnvironment(Base):
    __tablename__ = "alm_environments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    env_type: Mapped[EnvironmentType] = mapped_column(
        Enum(EnvironmentType), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_env_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("alm_environments.id", ondelete="SET NULL"), nullable=True
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    source_env: Mapped[Optional["ALMEnvironment"]] = relationship(
        "ALMEnvironment", remote_side="ALMEnvironment.id", lazy="selectin"
    )
    revision_tags: Mapped[list["RevisionTag"]] = relationship(
        "RevisionTag",
        back_populates="environment",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class RevisionTag(Base):
    __tablename__ = "revision_tags"
    __table_args__ = (
        UniqueConstraint("environment_id", "tag_name", name="uq_env_tag_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alm_environments.id", ondelete="CASCADE"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    environment: Mapped["ALMEnvironment"] = relationship(
        "ALMEnvironment", back_populates="revision_tags", lazy="selectin"
    )
    creator: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821


class PromotionRecord(Base):
    __tablename__ = "promotion_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    source_env_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alm_environments.id", ondelete="CASCADE"), nullable=False
    )
    target_env_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alm_environments.id", ondelete="CASCADE"), nullable=False
    )
    revision_tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("revision_tags.id", ondelete="CASCADE"), nullable=False
    )
    promoted_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[PromotionStatus] = mapped_column(
        Enum(PromotionStatus), default=PromotionStatus.pending, nullable=False
    )
    change_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source_env: Mapped["ALMEnvironment"] = relationship(
        "ALMEnvironment", foreign_keys=[source_env_id], lazy="selectin"
    )
    target_env: Mapped["ALMEnvironment"] = relationship(
        "ALMEnvironment", foreign_keys=[target_env_id], lazy="selectin"
    )
    revision_tag: Mapped["RevisionTag"] = relationship("RevisionTag", lazy="selectin")
    promoter: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
