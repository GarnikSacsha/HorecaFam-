from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BackgroundJobStatus, BackgroundJobType, EmailDeliveryStatus


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_background_jobs_id_organization_id"),
        UniqueConstraint("job_type", "idempotency_key", name="uq_background_jobs_type_key"),
        CheckConstraint("job_type = 'invitation_email'", name="job_type_allowed"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND payload ? 'invitation_id' "
            "AND payload ? 'token_version'",
            name="invitation_payload_required",
        ),
        CheckConstraint("priority >= 0", name="priority_nonnegative"),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts",
            name="attempt_counts_allowed",
        ),
        CheckConstraint(
            "status <> 'processing' OR "
            "(locked_by IS NOT NULL AND locked_at IS NOT NULL AND started_at IS NOT NULL)",
            name="processing_lease_present",
        ),
        CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL", name="completed_at_present"
        ),
        CheckConstraint("status <> 'failed' OR failed_at IS NOT NULL", name="failed_at_present"),
        CheckConstraint(
            "NOT (completed_at IS NOT NULL AND failed_at IS NOT NULL)",
            name="terminal_timestamp_exclusive",
        ),
        Index(
            "ix_background_jobs_claim",
            "status",
            "next_run_at",
            "priority",
            "created_at",
        ),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=BackgroundJobType.INVITATION_EMAIL.value,
        server_default=text("'invitation_email'"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=BackgroundJobStatus.PENDING.value,
        server_default=text("'pending'"),
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_by: Mapped[str | None] = mapped_column(String(255))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["background_jobs.id", "background_jobs.organization_id"],
            name="fk_email_deliveries_job_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["invitation_id", "organization_id"],
            ["invitations.id", "invitations.organization_id"],
            name="fk_email_deliveries_invitation_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("job_id", name="uq_email_deliveries_job_id"),
        CheckConstraint("message_type = 'invitation_email'", name="message_type_allowed"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'delivered', 'bounced', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "status <> 'accepted' OR accepted_by_provider_at IS NOT NULL",
            name="accepted_at_present",
        ),
        CheckConstraint(
            "status <> 'delivered' OR delivered_at IS NOT NULL", name="delivered_at_present"
        ),
        CheckConstraint("status <> 'bounced' OR bounced_at IS NOT NULL", name="bounced_at_present"),
        CheckConstraint("status <> 'failed' OR failed_at IS NOT NULL", name="failed_at_present"),
        Index("ix_email_deliveries_invitation_created", "invitation_id", "created_at"),
        Index("ix_email_deliveries_provider_message", "provider", "provider_message_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    invitation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=BackgroundJobType.INVITATION_EMAIL.value,
        server_default=text("'invitation_email'"),
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=EmailDeliveryStatus.PENDING.value,
        server_default=text("'pending'"),
    )
    accepted_by_provider_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
