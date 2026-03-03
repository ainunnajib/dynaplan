import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SSOProvider(Base):
    __tablename__ = "sso_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "saml" or "oidc"
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_url: Mapped[str] = mapped_column(String(500), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_encrypted: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    certificate: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_provision: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_role: Mapped[str] = mapped_column(String(50), default="viewer", nullable=False)
    domain_allowlist: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", lazy="selectin")  # noqa: F821


class SSOSession(Base):
    __tablename__ = "sso_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sso_providers.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    session_token: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821
    provider: Mapped["SSOProvider"] = relationship("SSOProvider", lazy="selectin")
