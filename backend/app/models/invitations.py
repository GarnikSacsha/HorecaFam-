from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'revoked')", name="status_allowed"),
        CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        CheckConstraint("token_version >= 1", name="token_version_positive"),
        CheckConstraint("token_key_index >= 0", name="token_key_index_nonnegative"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        CheckConstraint(
            "status <> 'accepted' OR accepted_at IS NOT NULL", name="accepted_timestamp"
        ),
        CheckConstraint("status <> 'revoked' OR revoked_at IS NOT NULL", name="revoked_timestamp"),
        UniqueConstraint("id", "organization_id", name="uq_invitations_id_organization_id"),
        Index(
            "uq_invitations_pending_organization_email",
            "organization_id",
            "email_normalized",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_invitations_organization_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    token_key_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    invited_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiIdempotencyRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "action",
            "key",
            name="uq_api_idempotency_scope_action_key",
        ),
        CheckConstraint("length(request_fingerprint) = 64", name="request_fingerprint_length"),
        CheckConstraint(
            "response_status >= 200 AND response_status <= 599", name="response_status_allowed"
        ),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_api_idempotency_expires_at", "expires_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvitationRateLimitBucket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invitation_rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint("action", "subject_hash", name="uq_invitation_rate_limit_action_subject"),
        CheckConstraint("action IN ('create', 'resend', 'validate')", name="action_allowed"),
        CheckConstraint("length(subject_hash) = 64", name="subject_hash_length"),
        CheckConstraint("request_count >= 0", name="request_count_nonnegative"),
        Index("ix_invitation_rate_limit_blocked_until", "blocked_until"),
    )

    action: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
