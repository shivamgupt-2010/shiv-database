import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.models.base import Base


class OAuthClient(Base):
    """
    Registered third-party or first-party OAuth 2.0 / OpenID Connect client application.
    Supports both public clients (SPA, Mobile) and confidential clients (Web server with backend).
    """
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    client_secret_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    client_name: Mapped[str] = mapped_column(String(150), nullable=False)
    client_uri: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logo_uri: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    redirect_uris_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    allowed_scopes: Mapped[str] = mapped_column(String(255), default="openid profile email", nullable=False)
    client_type: Mapped[str] = mapped_column(String(20), default="confidential", nullable=False)  # "confidential" or "public"
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)  # "active", "suspended", "revoked"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_confidential(self) -> bool:
        return self.client_type == "confidential"


class OAuthAuthorizationCode(Base):
    """
    Single-use, short-lived authorization code with PKCE verification binding.
    """
    __tablename__ = "oauth_authorization_codes"

    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    scope: Mapped[str] = mapped_column(String(255), default="openid", nullable=False)
    code_challenge: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    code_challenge_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # "S256"
    nonce: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @property
    def is_expired(self) -> bool:
        exp = self.expires_at
        if exp.tzinfo is None:
            return datetime.now(timezone.utc).replace(tzinfo=None) > exp
        return datetime.now(timezone.utc) > exp


class OAuthConsentGrant(Base):
    """
    Persistent user consent grant for an application.
    Allows users to manage and revoke third-party app permissions.
    """
    __tablename__ = "oauth_consent_grants"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    granted_scopes: Mapped[str] = mapped_column(String(255), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OAuthToken(Base):
    """
    Issued OAuth access and refresh tokens for revocation and introspection.
    """
    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String(30), default="access_token", nullable=False)  # "access_token" or "refresh_token"
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @property
    def is_active(self) -> bool:
        return not self.revoked and datetime.now(timezone.utc) <= self.expires_at
