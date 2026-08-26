"""Додати схему автентифікації та контролю доступу Stage 2.

Revision ID: 0003_auth_security
Revises: 0002_identity_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_auth_security"
down_revision: str | None = "0002_identity_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_access",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "scope IN ('organization_admin', 'platform_operator')",
            name=op.f("ck_admin_access_scope_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name=op.f("ck_admin_access_status_allowed"),
        ),
        sa.CheckConstraint(
            "((scope = 'organization_admin' AND organization_id IS NOT NULL) "
            "OR (scope = 'platform_operator' AND organization_id IS NULL))",
            name=op.f("ck_admin_access_scope_organization_consistent"),
        ),
        sa.CheckConstraint(
            "((status = 'active' AND revoked_at IS NULL) "
            "OR (status = 'revoked' AND revoked_at IS NOT NULL))",
            name=op.f("ck_admin_access_status_timestamp_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_admin_access_granted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_admin_access_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_admin_access_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_access")),
    )
    op.create_index(op.f("ix_admin_access_organization_id"), "admin_access", ["organization_id"])
    op.create_index(op.f("ix_admin_access_user_id"), "admin_access", ["user_id"])
    op.create_index(
        "uq_admin_access_active_organization",
        "admin_access",
        ["user_id", "organization_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'organization_admin' AND status = 'active'"),
    )
    op.create_index(
        "uq_admin_access_active_platform",
        "admin_access",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'platform_operator' AND status = 'active'"),
    )

    op.create_table(
        "sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=64), nullable=True),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(token_hash) = 64", name=op.f("ck_sessions_token_hash_length")),
        sa.CheckConstraint(
            "length(csrf_token_hash) = 64", name=op.f("ck_sessions_csrf_token_hash_length")
        ),
        sa.CheckConstraint(
            "absolute_expires_at > created_at", name=op.f("ck_sessions_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoke_reason IS NOT NULL",
            name=op.f("ck_sessions_revocation_reason_present"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("csrf_token_hash", name=op.f("uq_sessions_csrf_token_hash")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_user_active", "sessions", ["user_id", "revoked_at", "absolute_expires_at"]
    )

    op.create_table(
        "mfa_credentials",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), server_default="totp", nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_used_counter", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("type = 'totp'", name=op.f("ck_mfa_credentials_type_allowed")),
        sa.CheckConstraint(
            "length(secret_encrypted) > 0", name=op.f("ck_mfa_credentials_secret_not_blank")
        ),
        sa.CheckConstraint(
            "last_used_counter IS NULL OR last_used_counter >= 0",
            name=op.f("ck_mfa_credentials_counter_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mfa_credentials_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_credentials")),
    )
    op.create_index(op.f("ix_mfa_credentials_user_id"), "mfa_credentials", ["user_id"])
    op.create_index(
        "uq_mfa_credentials_active_confirmed_user",
        "mfa_credentials",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("confirmed_at IS NOT NULL AND disabled_at IS NULL"),
    )

    op.create_table(
        "mfa_challenges",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "length(token_hash) = 64", name=op.f("ck_mfa_challenges_token_hash_length")
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_mfa_challenges_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "failed_attempts >= 0 AND failed_attempts <= 5",
            name=op.f("ck_mfa_challenges_failed_attempts_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mfa_challenges_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_challenges")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_mfa_challenges_token_hash")),
    )
    op.create_index(op.f("ix_mfa_challenges_user_id"), "mfa_challenges", ["user_id"])
    op.create_index(
        "ix_mfa_challenges_user_active", "mfa_challenges", ["user_id", "used_at", "expires_at"]
    )

    op.create_table(
        "auth_rate_limit_buckets",
        sa.Column("action", sa.String(length=32), server_default="login", nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "action = 'login'", name=op.f("ck_auth_rate_limit_buckets_action_allowed")
        ),
        sa.CheckConstraint(
            "length(subject_hash) = 64", name=op.f("ck_auth_rate_limit_buckets_subject_hash_length")
        ),
        sa.CheckConstraint(
            "failure_count >= 0", name=op.f("ck_auth_rate_limit_buckets_failure_count_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_rate_limit_buckets")),
        sa.UniqueConstraint("action", "subject_hash", name="uq_auth_rate_limit_action_subject"),
    )
    op.create_index(
        "ix_auth_rate_limit_blocked_until", "auth_rate_limit_buckets", ["blocked_until"]
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limit_blocked_until", table_name="auth_rate_limit_buckets")
    op.drop_table("auth_rate_limit_buckets")
    op.drop_index("ix_mfa_challenges_user_active", table_name="mfa_challenges")
    op.drop_index(op.f("ix_mfa_challenges_user_id"), table_name="mfa_challenges")
    op.drop_table("mfa_challenges")
    op.drop_index("uq_mfa_credentials_active_confirmed_user", table_name="mfa_credentials")
    op.drop_index(op.f("ix_mfa_credentials_user_id"), table_name="mfa_credentials")
    op.drop_table("mfa_credentials")
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("uq_admin_access_active_platform", table_name="admin_access")
    op.drop_index("uq_admin_access_active_organization", table_name="admin_access")
    op.drop_index(op.f("ix_admin_access_user_id"), table_name="admin_access")
    op.drop_index(op.f("ix_admin_access_organization_id"), table_name="admin_access")
    op.drop_table("admin_access")
