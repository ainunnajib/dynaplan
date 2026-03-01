import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sso import SSOProvider, SSOSession
from app.models.user import User
from app.services.auth import create_access_token, get_user_by_email, hash_password


async def create_provider(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    provider_type: str,
    display_name: str,
    issuer_url: str,
    client_id: str,
    client_secret: Optional[str] = None,
    metadata_url: Optional[str] = None,
    certificate: Optional[str] = None,
    auto_provision: bool = True,
    default_role: str = "viewer",
    domain_allowlist: Optional[List[str]] = None,
) -> SSOProvider:
    provider = SSOProvider(
        workspace_id=workspace_id,
        provider_type=provider_type,
        display_name=display_name,
        issuer_url=issuer_url,
        client_id=client_id,
        client_secret_encrypted=client_secret,
        metadata_url=metadata_url,
        certificate=certificate,
        auto_provision=auto_provision,
        default_role=default_role,
        domain_allowlist=domain_allowlist,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def get_provider(
    db: AsyncSession, provider_id: uuid.UUID
) -> Optional[SSOProvider]:
    result = await db.execute(
        select(SSOProvider).where(SSOProvider.id == provider_id)
    )
    return result.scalar_one_or_none()


async def get_provider_for_workspace(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Optional[SSOProvider]:
    result = await db.execute(
        select(SSOProvider).where(SSOProvider.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def update_provider(
    db: AsyncSession, provider_id: uuid.UUID, **updates: Any
) -> Optional[SSOProvider]:
    provider = await get_provider(db, provider_id)
    if provider is None:
        return None

    field_map = {
        "provider_type": "provider_type",
        "display_name": "display_name",
        "issuer_url": "issuer_url",
        "client_id": "client_id",
        "client_secret": "client_secret_encrypted",
        "metadata_url": "metadata_url",
        "certificate": "certificate",
        "auto_provision": "auto_provision",
        "default_role": "default_role",
        "domain_allowlist": "domain_allowlist",
        "is_active": "is_active",
    }

    for key, value in updates.items():
        if value is not None and key in field_map:
            setattr(provider, field_map[key], value)

    await db.commit()
    await db.refresh(provider)
    return provider


async def delete_provider(db: AsyncSession, provider_id: uuid.UUID) -> bool:
    provider = await get_provider(db, provider_id)
    if provider is None:
        return False
    await db.delete(provider)
    await db.commit()
    return True


async def initiate_sso_login(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Optional[Dict[str, str]]:
    provider = await get_provider_for_workspace(db, workspace_id)
    if provider is None or not provider.is_active:
        return None

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": provider.client_id,
        "redirect_uri": f"http://localhost:8000/sso/{workspace_id}/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    redirect_url = f"{provider.issuer_url}/authorize?{urlencode(params)}"
    return {"redirect_url": redirect_url, "state": state}


async def provision_user(
    db: AsyncSession,
    email: str,
    full_name: str,
    provider_id: uuid.UUID,
    external_id: str,
    default_role: str = "viewer",
) -> tuple:
    """Find or create a user from SSO. Returns (user, was_provisioned)."""
    from app.models.user import UserRole

    existing = await get_user_by_email(db, email)
    if existing is not None:
        return existing, False

    # Auto-provision: create user with random password (SSO users don't use password login)
    role = UserRole.viewer
    if default_role == "admin":
        role = UserRole.admin
    elif default_role == "modeler":
        role = UserRole.modeler

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, True


async def handle_sso_callback(
    db: AsyncSession,
    provider_id: uuid.UUID,
    code: str,
    state: str,
) -> Optional[Dict[str, Any]]:
    """
    Simulate processing the SSO callback. In production this would exchange
    the code for an ID token and validate it. Here we simulate by deriving
    user info from the code (treating it as 'email:full_name').
    """
    provider = await get_provider(db, provider_id)
    if provider is None or not provider.is_active:
        return None

    # Simulate token exchange: code format is "email:full_name:external_id"
    # In real OIDC, we'd POST to provider.issuer_url/token and validate the JWT
    parts = code.split(":", 2)
    if len(parts) < 2:
        # fallback: treat code as external_id, generate dummy user info
        email = f"sso-user-{code[:8]}@sso.example.com"
        full_name = "SSO User"
        external_id = code
    else:
        email = parts[0]
        full_name = parts[1] if len(parts) > 1 else "SSO User"
        external_id = parts[2] if len(parts) > 2 else code

    # Check domain allowlist
    if provider.domain_allowlist:
        allowed = check_domain_allowed(provider, email)
        if not allowed:
            return {"error": "domain_not_allowed"}

    # Check auto_provision
    if not provider.auto_provision:
        # Only allow existing users
        existing = await get_user_by_email(db, email)
        if existing is None:
            return {"error": "user_not_provisioned"}
        user = existing
        provisioned = False
    else:
        user, provisioned = await provision_user(
            db, email, full_name, provider_id, external_id, provider.default_role
        )

    # Create SSO session
    session_token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
    session = SSOSession(
        user_id=user.id,
        provider_id=provider_id,
        external_id=external_id,
        session_token=session_token,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()

    # Generate JWT access token (same as regular auth)
    access_token = create_access_token(str(user.id))

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "provisioned": provisioned,
    }


async def validate_sso_session(
    db: AsyncSession, session_token: str
) -> Optional[SSOSession]:
    """Return the session if valid and not expired, else None."""
    result = await db.execute(
        select(SSOSession).where(SSOSession.session_token == session_token)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    now = datetime.now(timezone.utc)
    expires = session.expires_at
    # SQLite returns naive datetimes; make it timezone-aware for comparison
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return None
    return session


async def revoke_sso_session(
    db: AsyncSession, session_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(SSOSession).where(SSOSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return False
    await db.delete(session)
    await db.commit()
    return True


def check_domain_allowed(provider: SSOProvider, email: str) -> bool:
    """Check whether the email's domain is in the provider's allowlist."""
    if not provider.domain_allowlist:
        return True
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1].lower()
    return domain in [d.lower() for d in provider.domain_allowlist]
