"""Add durable Job attempt and correlation runtime.

Revision ID: 0018_job_runtime
Revises: 0017_employee_lifecycle
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_job_runtime"
down_revision: str | None = "0017_employee_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREVIOUS_JOB_TYPES = (
    "job_type IN ('invitation_email', 'training_assignment_notification', "
    "'training_rollout_notification', 'password_reset_email')"
)
CURRENT_JOB_TYPES = (
    "job_type IN ('invitation_email', 'training_assignment_notification', "
    "'training_rollout_notification', 'password_reset_email', 'attempt_expiry', "
    "'retake_deadline_projection', 'security_record_cleanup', 'audit_retention')"
)
PREVIOUS_PAYLOADS = (
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
    "AND payload - ARRAY['password_reset_token_id'] = '{}'::jsonb))"
)
CURRENT_PAYLOADS = (
    PREVIOUS_PAYLOADS[:-1] + " OR (job_type = 'attempt_expiry' "
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
    "AND payload - ARRAY['cutoff_at', 'dry_run'] = '{}'::jsonb))"
)


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"),
        "background_jobs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_background_jobs_job_type_allowed"),
        "background_jobs",
        type_="check",
    )
    op.add_column("background_jobs", sa.Column("request_id", sa.String(length=36)))
    op.create_check_constraint(
        op.f("ck_background_jobs_job_type_allowed"),
        "background_jobs",
        CURRENT_JOB_TYPES,
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"),
        "background_jobs",
        CURRENT_PAYLOADS,
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_request_id_uuid"),
        "background_jobs",
        "request_id IS NULL OR request_id ~ "
        "'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'",
    )

    op.create_table(
        "job_attempts",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("heartbeat_last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "outcome",
            sa.String(length=32),
            server_default="processing",
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=64)),
        sa.Column("error_message", sa.String(length=500)),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "attempt_number BETWEEN 1 AND 5",
            name=op.f("ck_job_attempts_attempt_number_allowed"),
        ),
        sa.CheckConstraint(
            "outcome IN ('processing', 'completed', 'retry_scheduled', 'failed', 'interrupted')",
            name=op.f("ck_job_attempts_outcome_allowed"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_job_attempts_outcome_state"),
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name=op.f("ck_job_attempts_error_code_format"),
        ),
        sa.CheckConstraint(
            "error_message IS NULL OR (error_message = btrim(error_message) "
            "AND length(error_message) BETWEEN 1 AND 500)",
            name=op.f("ck_job_attempts_error_message_bounded"),
        ),
        sa.CheckConstraint(
            "heartbeat_last_seen_at IS NULL OR heartbeat_last_seen_at >= started_at",
            name=op.f("ck_job_attempts_heartbeat_after_start"),
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name=op.f("ck_job_attempts_finished_after_start"),
        ),
        sa.CheckConstraint(
            "next_retry_at IS NULL OR (finished_at IS NOT NULL AND next_retry_at >= finished_at)",
            name=op.f("ck_job_attempts_retry_after_finish"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["background_jobs.id"],
            name=op.f("fk_job_attempts_job_id_background_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_attempts")),
        sa.UniqueConstraint(
            "job_id",
            "attempt_number",
            name="uq_job_attempts_job_number",
        ),
    )
    op.create_index(
        "ix_job_attempts_job_started",
        "job_attempts",
        ["job_id", "started_at"],
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION protect_job_attempt_history() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'job attempts are append-only';
                END IF;
                IF OLD.finished_at IS NOT NULL THEN
                    RAISE EXCEPTION 'finalized job attempts are immutable';
                END IF;
                IF NEW.id IS DISTINCT FROM OLD.id
                   OR NEW.job_id IS DISTINCT FROM OLD.job_id
                   OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
                   OR NEW.worker_id IS DISTINCT FROM OLD.worker_id
                   OR NEW.started_at IS DISTINCT FROM OLD.started_at THEN
                    RAISE EXCEPTION 'job attempt identity is immutable';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        "CREATE TRIGGER trg_job_attempts_append_only "
        "BEFORE UPDATE OR DELETE ON job_attempts "
        "FOR EACH ROW EXECUTE FUNCTION protect_job_attempt_history()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_job_attempts_append_only ON job_attempts")
    op.execute("DROP FUNCTION IF EXISTS protect_job_attempt_history()")
    op.drop_index("ix_job_attempts_job_started", table_name="job_attempts")
    op.drop_table("job_attempts")

    op.drop_constraint(
        op.f("ck_background_jobs_request_id_uuid"),
        "background_jobs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"),
        "background_jobs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_background_jobs_job_type_allowed"),
        "background_jobs",
        type_="check",
    )
    op.execute(
        sa.text(
            "DELETE FROM background_jobs WHERE job_type IN "
            "('attempt_expiry', 'retake_deadline_projection', "
            "'security_record_cleanup', 'audit_retention')"
        )
    )
    op.drop_column("background_jobs", "request_id")
    op.create_check_constraint(
        op.f("ck_background_jobs_job_type_allowed"),
        "background_jobs",
        PREVIOUS_JOB_TYPES,
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"),
        "background_jobs",
        PREVIOUS_PAYLOADS,
    )
