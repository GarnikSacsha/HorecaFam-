"""Додати схему збереження ідентичності для Stage 1.

Revision ID: 0002_identity_persistence
Revises: 0001_stage0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity_persistence"
down_revision: str | None = "0001_stage0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column[sa.DateTime], sa.Column[sa.DateTime]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("default_locale", sa.String(length=8), server_default="uk", nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "default_locale IN ('uk', 'en')",
            name=op.f("ck_organizations_locale_allowed"),
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_organizations_name_not_blank")),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name=op.f("ck_organizations_status_allowed"),
        ),
        sa.CheckConstraint(
            "length(btrim(timezone)) > 0",
            name=op.f("ck_organizations_timezone_not_blank"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_table(
        "users",
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("preferred_locale", sa.String(length=8), server_default="uk", nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("length(email_normalized) > 0", name=op.f("ck_users_email_not_blank")),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email_normalized))",
            name=op.f("ck_users_email_normalized"),
        ),
        sa.CheckConstraint(
            "preferred_locale IN ('uk', 'en')", name=op.f("ck_users_locale_allowed")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
    )
    op.create_table(
        "locations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("length(btrim(name)) > 0", name=op.f("ck_locations_name_not_blank")),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name=op.f("ck_locations_status_allowed"),
        ),
        sa.CheckConstraint(
            "length(btrim(timezone)) > 0",
            name=op.f("ck_locations_timezone_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_locations_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.UniqueConstraint("id", "organization_id", name="uq_locations_id_organization_id"),
    )
    op.create_index("ix_locations_organization_id", "locations", ["organization_id"])
    op.create_table(
        "operational_roles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_uk", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "length(btrim(code)) > 0",
            name=op.f("ck_operational_roles_code_not_blank"),
        ),
        sa.CheckConstraint(
            "code = lower(btrim(code))",
            name=op.f("ck_operational_roles_code_normalized"),
        ),
        sa.CheckConstraint(
            "length(btrim(name_uk)) > 0",
            name=op.f("ck_operational_roles_name_uk_not_blank"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name=op.f("ck_operational_roles_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_operational_roles_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operational_roles"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_operational_roles_id_organization_id",
        ),
    )
    op.create_index(
        "ix_operational_roles_organization_id",
        "operational_roles",
        ["organization_id"],
    )
    op.create_index(
        "uq_operational_roles_active_code",
        "operational_roles",
        ["organization_id", "code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'disabled')",
            name=op.f("ck_organization_memberships_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status <> 'active' OR (activated_at IS NOT NULL AND disabled_at IS NULL))",
            name=op.f("ck_organization_memberships_active_timestamps"),
        ),
        sa.CheckConstraint(
            "(status <> 'disabled' OR disabled_at IS NOT NULL)",
            name=op.f("ck_organization_memberships_disabled_timestamp"),
        ),
        sa.CheckConstraint(
            "(status <> 'pending' OR (activated_at IS NULL AND disabled_at IS NULL))",
            name=op.f("ck_organization_memberships_pending_timestamps"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_memberships_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_organization_memberships_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_organization_memberships_id_organization_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_organization_user",
        ),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_memberships_user_id",
        "organization_memberships",
        ["user_id"],
    )
    op.create_table(
        "employee_profiles",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("operational_role_id", sa.Uuid(), nullable=True),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_employee_profiles_location_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_employee_profiles_membership_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            name="fk_employee_profiles_role_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employee_profiles"),
        sa.UniqueConstraint("membership_id", name="uq_employee_profiles_membership_id"),
    )
    op.create_index(
        "ix_employee_profiles_location_id",
        "employee_profiles",
        ["location_id"],
    )
    op.create_index(
        "ix_employee_profiles_membership_id",
        "employee_profiles",
        ["membership_id"],
    )
    op.create_index(
        "ix_employee_profiles_operational_role_id",
        "employee_profiles",
        ["operational_role_id"],
    )
    op.create_index(
        "ix_employee_profiles_organization_id",
        "employee_profiles",
        ["organization_id"],
    )
    op.create_table(
        "audit_events",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("old_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system', 'worker', 'cron')",
            name=op.f("ck_audit_events_actor_type_allowed"),
        ),
        sa.CheckConstraint(
            "((actor_type = 'user' AND actor_user_id IS NOT NULL) "
            "OR (actor_type <> 'user' AND actor_user_id IS NULL))",
            name=op.f("ck_audit_events_actor_identity_consistent"),
        ),
        sa.CheckConstraint(
            "length(btrim(action)) > 0", name=op.f("ck_audit_events_action_not_blank")
        ),
        sa.CheckConstraint(
            "length(btrim(target_type)) > 0",
            name=op.f("ck_audit_events_target_type_not_blank"),
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failed')",
            name=op.f("ck_audit_events_outcome_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_target", "audit_events", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_target", table_name="audit_events")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_employee_profiles_organization_id", table_name="employee_profiles")
    op.drop_index("ix_employee_profiles_operational_role_id", table_name="employee_profiles")
    op.drop_index("ix_employee_profiles_membership_id", table_name="employee_profiles")
    op.drop_index("ix_employee_profiles_location_id", table_name="employee_profiles")
    op.drop_table("employee_profiles")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index(
        "ix_organization_memberships_organization_id",
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")
    op.drop_index("uq_operational_roles_active_code", table_name="operational_roles")
    op.drop_index("ix_operational_roles_organization_id", table_name="operational_roles")
    op.drop_table("operational_roles")
    op.drop_index("ix_locations_organization_id", table_name="locations")
    op.drop_table("locations")
    op.drop_table("users")
    op.drop_table("organizations")
