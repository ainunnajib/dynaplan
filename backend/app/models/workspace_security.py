import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkspaceSecurityPolicy(Base):
    __tablename__ = "workspace_security_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    ip_allowlist: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    enforce_ip_allowlist: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    require_client_certificate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", lazy="selectin")  # noqa: F821


class WorkspaceClientCertificate(Base):
    __tablename__ = "workspace_client_certificates"
    __table_args__ = (
        Index(
            "ix_workspace_client_certificates_workspace_active",
            "workspace_id",
            "is_active",
        ),
        Index(
            "ix_workspace_client_certificates_workspace_fingerprint",
            "workspace_id",
            "fingerprint_sha256",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fingerprint_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issuer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    not_before: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    not_after: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", lazy="selectin")  # noqa: F821
