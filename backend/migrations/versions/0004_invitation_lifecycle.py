"""Додати життєвий цикл запрошень Stage 3.

Revision ID: 0004_invitation_lifecycle
Revises: 0003_auth_security
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_invitation_lifecycle"
down_revision: str | None = "0003_auth_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("token_key_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')",
            name=op.f("ck_invitations_status_allowed"),
        ),
        sa.CheckConstraint(
            "length(token_hash) = 64", name=op.f("ck_invitations_token_hash_length")
        ),
        sa.CheckConstraint(
            "token_version >= 1", name=op.f("ck_invitations_token_version_positive")
        ),
        sa.CheckConstraint(
            "token_key_index >= 0", name=op.f("ck_invitations_token_key_index_nonnegative")
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_invitations_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "status <> 'accepted' OR accepted_at IS NOT NULL",
            name=op.f("ck_invitations_accepted_timestamp"),
        ),
        sa.CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name=op.f("ck_invitations_revoked_timestamp"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_invitations_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_invited_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(op.f("ix_invitations_organization_id"), "invitations", ["organization_id"])
    op.create_index(
        op.f("ix_invitations_invited_by_user_id"), "invitations", ["invited_by_user_id"]
    )
    op.create_index(
        "ix_invitations_organization_status", "invitations", ["organization_id", "status"]
    )
    op.create_index(
        "uq_invitations_pending_organization_email",
        "invitations",
        ["organization_id", "email_normalized"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "api_idempotency_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name=op.f("ck_api_idempotency_records_request_fingerprint_length"),
        ),
        sa.CheckConstraint(
            "response_status >= 200 AND response_status <= 599",
            name=op.f("ck_api_idempotency_records_response_status_allowed"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_api_idempotency_records_expiry_after_creation")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_api_idempotency_records_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_api_idempotency_records_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_idempotency_records")),
        sa.UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "action",
            "key",
            name="uq_api_idempotency_scope_action_key",
        ),
    )
    op.create_index("ix_api_idempotency_expires_at", "api_idempotency_records", ["expires_at"])

    op.create_table(
        "invitation_rate_limit_buckets",
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action IN ('create', 'resend', 'validate')",
            name=op.f("ck_invitation_rate_limit_buckets_action_allowed"),
        ),
        sa.CheckConstraint(
            "length(subject_hash) = 64",
            name=op.f("ck_invitation_rate_limit_buckets_subject_hash_length"),
        ),
        sa.CheckConstraint(
            "request_count >= 0",
            name=op.f("ck_invitation_rate_limit_buckets_request_count_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation_rate_limit_buckets")),
        sa.UniqueConstraint(
            "action", "subject_hash", name="uq_invitation_rate_limit_action_subject"
        ),
    )
    op.create_index(
        "ix_invitation_rate_limit_blocked_until", "invitation_rate_limit_buckets", ["blocked_until"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invitation_rate_limit_blocked_until", table_name="invitation_rate_limit_buckets"
    )
    op.drop_table("invitation_rate_limit_buckets")
    op.drop_index("ix_api_idempotency_expires_at", table_name="api_idempotency_records")
    op.drop_table("api_idempotency_records")
    op.drop_index("uq_invitations_pending_organization_email", table_name="invitations")
    op.drop_index("ix_invitations_organization_status", table_name="invitations")
    op.drop_index(op.f("ix_invitations_invited_by_user_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_organization_id"), table_name="invitations")
    op.drop_table("invitations")
