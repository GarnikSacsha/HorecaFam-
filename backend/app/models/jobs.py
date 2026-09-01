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
from app.models.enums import (
    BackgroundJobStatus,
    BackgroundJobType,
    EmailDeliveryStatus,
    JobAttemptOutcome,
)


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_background_jobs_id_organization_id"),
        UniqueConstraint("job_type", "idempotency_key", name="uq_background_jobs_type_key"),
        CheckConstraint(
            "job_type IN ('invitation_email', 'training_assignment_notification', "
            "'training_rollout_notification', 'password_reset_email', 'attempt_expiry', "
            "'retake_deadline_projection', 'security_record_cleanup', 'audit_retention')",
            name="job_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND ("
            "(job_type = 'invitation_email' "
            "AND jsonb_typeof(payload->'invitation_id') = 'string' "
            "AND jsonb_typeof(payload->'token_version') = 'number' "
            "AND payload - ARRAY['invitation_id', 'token_version'] = '{}'::jsonb) OR "
            "(job_type = 'training_assignment_notification' "
            "AND jsonb_typeof(payload->'assignment_id') = 'string' "
            "AND jsonb_typeof(payload->'template_code') = 'string' "
            "AND length(payload->>'template_code') BETWEEN 1 AND 64 "
            "AND payload->>'locale' IN ('uk', 'en') "
            "AND payload - ARRAY['assignment_id', 'template_code', 'locale'] = '{}'::jsonb) OR "
            "(job_type = 'training_rollout_notification' "
            "AND jsonb_typeof(payload->'rollout_id') = 'string' "
            "AND jsonb_typeof(payload->'assignment_id') = 'string' "
            "AND jsonb_typeof(payload->'template_code') = 'string' "
            "AND length(payload->>'template_code') BETWEEN 1 AND 64 "
            "AND payload->>'locale' IN ('uk', 'en') "
            "AND payload - ARRAY['rollout_id', 'assignment_id', 'template_code', 'locale'] "
            "= '{}'::jsonb) OR "
            "(job_type = 'password_reset_email' "
            "AND jsonb_typeof(payload->'password_reset_token_id') = 'string' "
            "AND payload - ARRAY['password_reset_token_id'] = '{}'::jsonb) OR "
            "(job_type = 'attempt_expiry' "
            "AND jsonb_typeof(payload->'cutoff_at') = 'string' "
            "AND payload - ARRAY['cutoff_at'] = '{}'::jsonb) OR "
            "(job_type = 'retake_deadline_projection' "
            "AND jsonb_typeof(payload->'projected_at') = 'string' "
            "AND payload - ARRAY['projected_at'] = '{}'::jsonb) OR "
            "(job_type = 'security_record_cleanup' "
            "AND jsonb_typeof(payload->'cutoff_at') = 'string' "
            "AND payload - ARRAY['cutoff_at'] = '{}'::jsonb) OR "
            "(job_type = 'audit_retention' "
            "AND jsonb_typeof(payload->'cutoff_at') = 'string' "
            "AND jsonb_typeof(payload->'dry_run') = 'boolean' "
            "AND payload - ARRAY['cutoff_at', 'dry_run'] = '{}'::jsonb))",
            name="payload_matches_job_type",
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
        CheckConstraint(
            "request_id IS NULL OR request_id ~ "
            "'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'",
            name="request_id_uuid",
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
    request_id: Mapped[str | None] = mapped_column(String(36))
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


class JobAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempts_job_number"),
        CheckConstraint(
            "attempt_number BETWEEN 1 AND 5",
            name="attempt_number_allowed",
        ),
        CheckConstraint(
            "outcome IN ('processing', 'completed', 'retry_scheduled', 'failed', 'interrupted')",
            name="outcome_allowed",
        ),
        CheckConstraint(
            "(outcome = 'processing' AND finished_at IS NULL "
            "AND error_code IS NULL AND error_message IS NULL AND next_retry_at IS NULL) OR "
            "(outcome = 'completed' AND finished_at IS NOT NULL "
            "AND error_code IS NULL AND error_message IS NULL AND next_retry_at IS NULL) OR "
            "(outcome = 'retry_scheduled' AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL AND next_retry_at IS NOT NULL) OR "
            "(outcome = 'failed' AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL AND next_retry_at IS NULL) OR "
            "(outcome = 'interrupted' AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL AND next_retry_at IS NOT NULL)",
            name="outcome_state",
        ),
        CheckConstraint(
            "error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name="error_code_format",
        ),
        CheckConstraint(
            "error_message IS NULL OR (error_message = btrim(error_message) "
            "AND length(error_message) BETWEEN 1 AND 500)",
            name="error_message_bounded",
        ),
        CheckConstraint(
            "heartbeat_last_seen_at IS NULL OR heartbeat_last_seen_at >= started_at",
            name="heartbeat_after_start",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_after_start",
        ),
        CheckConstraint(
            "next_retry_at IS NULL OR (finished_at IS NOT NULL AND next_retry_at >= finished_at)",
            name="retry_after_finish",
        ),
        Index("ix_job_attempts_job_started", "job_id", "started_at"),
    )

    job_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("background_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    heartbeat_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=JobAttemptOutcome.PROCESSING.value,
        server_default=text("'processing'"),
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id"],
            ["background_jobs.id"],
            name="fk_email_deliveries_job",
            ondelete="RESTRICT",
        ),
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
        ForeignKeyConstraint(
            ["password_reset_token_id"],
            ["password_reset_tokens.id"],
            name="fk_email_deliveries_password_reset_token",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("job_id", name="uq_email_deliveries_job_id"),
        CheckConstraint(
            "message_type IN ('invitation_email', 'password_reset_email')",
            name="message_type_allowed",
        ),
        CheckConstraint(
            "num_nonnulls(invitation_id, password_reset_token_id) = 1",
            name="exactly_one_source",
        ),
        CheckConstraint(
            "(message_type = 'invitation_email' AND organization_id IS NOT NULL "
            "AND invitation_id IS NOT NULL AND password_reset_token_id IS NULL) OR "
            "(message_type = 'password_reset_email' AND organization_id IS NULL "
            "AND invitation_id IS NULL AND password_reset_token_id IS NOT NULL)",
            name="source_matches_message_type",
        ),
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
        Index(
            "ix_email_deliveries_password_reset_created",
            "password_reset_token_id",
            "created_at",
        ),
        Index("ix_email_deliveries_provider_message", "provider", "provider_message_id"),
    )

    organization_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    job_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    invitation_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    password_reset_token_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
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
