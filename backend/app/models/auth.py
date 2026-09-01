from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AccessStatus, AuthRateLimitAction, MfaCredentialType

if TYPE_CHECKING:
    from app.models.identity import Organization, User


class AdminAccess(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admin_access"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('organization_admin', 'platform_operator')",
            name="scope_allowed",
        ),
        CheckConstraint("status IN ('active', 'revoked')", name="status_allowed"),
        CheckConstraint(
            "((scope = 'organization_admin' AND organization_id IS NOT NULL) "
            "OR (scope = 'platform_operator' AND organization_id IS NULL))",
            name="scope_organization_consistent",
        ),
        CheckConstraint(
            "((status = 'active' AND revoked_at IS NULL) "
            "OR (status = 'revoked' AND revoked_at IS NOT NULL))",
            name="status_timestamp_consistent",
        ),
        Index(
            "uq_admin_access_active_organization",
            "user_id",
            "organization_id",
            unique=True,
            postgresql_where=text("scope = 'organization_admin' AND status = 'active'"),
        ),
        Index(
            "uq_admin_access_active_platform",
            "user_id",
            unique=True,
            postgresql_where=text("scope = 'platform_operator' AND status = 'active'"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AccessStatus.ACTIVE.value,
        server_default=text("'active'"),
    )
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(
        back_populates="admin_accesses",
        foreign_keys=[user_id],
    )
    organization: Mapped["Organization | None"] = relationship()


class Session(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        CheckConstraint("length(csrf_token_hash) = 64", name="csrf_token_hash_length"),
        CheckConstraint("absolute_expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint(
            "revoked_at IS NULL OR revoke_reason IS NOT NULL",
            name="revocation_reason_present",
        ),
        Index("ix_sessions_user_active", "user_id", "revoked_at", "absolute_expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(64))
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    user: Mapped["User"] = relationship(back_populates="sessions")


class MfaCredential(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mfa_credentials"
    __table_args__ = (
        CheckConstraint("type = 'totp'", name="type_allowed"),
        CheckConstraint("length(secret_encrypted) > 0", name="secret_not_blank"),
        CheckConstraint(
            "last_used_counter IS NULL OR last_used_counter >= 0",
            name="counter_nonnegative",
        ),
        Index(
            "uq_mfa_credentials_active_confirmed_user",
            "user_id",
            unique=True,
            postgresql_where=text("confirmed_at IS NOT NULL AND disabled_at IS NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MfaCredentialType.TOTP.value,
        server_default=text("'totp'"),
    )
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_counter: Mapped[int | None] = mapped_column(BigInteger)

    user: Mapped["User"] = relationship(back_populates="mfa_credentials")
    recovery_codes: Mapped[list["MfaRecoveryCode"]] = relationship(back_populates="mfa_credential")


class MfaRecoveryCode(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mfa_recovery_codes"
    __table_args__ = (
        CheckConstraint("length(code_hash) = 64", name="code_hash_length"),
        CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name="used_after_creation",
        ),
        Index(
            "ix_mfa_recovery_codes_credential_unused",
            "mfa_credential_id",
            "created_at",
            postgresql_where=text("used_at IS NULL"),
        ),
    )

    mfa_credential_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("mfa_credentials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    mfa_credential: Mapped["MfaCredential"] = relationship(back_populates="recovery_codes")


class MfaChallenge(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mfa_challenges"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint(
            "failed_attempts >= 0 AND failed_attempts <= 5",
            name="failed_attempts_allowed",
        ),
        Index("ix_mfa_challenges_user_active", "user_id", "used_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("'0'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="mfa_challenges")


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint(
            "num_nonnulls(used_at, revoked_at) <= 1",
            name="single_terminal_state",
        ),
        CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name="used_after_creation",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="revoked_after_creation",
        ),
        Index(
            "ix_password_reset_tokens_user_active",
            "user_id",
            "expires_at",
            postgresql_where=text("used_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")


class AuthRateLimitBucket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "auth_rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint("action", "subject_hash", name="uq_auth_rate_limit_action_subject"),
        CheckConstraint("action = 'login'", name="action_allowed"),
        CheckConstraint("length(subject_hash) = 64", name="subject_hash_length"),
        CheckConstraint("failure_count >= 0", name="failure_count_nonnegative"),
        Index("ix_auth_rate_limit_blocked_until", "blocked_until"),
    )

    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AuthRateLimitAction.LOGIN.value,
        server_default=text("'login'"),
    )
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("'0'"),
    )
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
