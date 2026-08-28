"""Додати аудиторії, призначення, завершення та розгортання навчання.

Revision ID: 0009_assignment_completion_rollout
Revises: 0008_training_content
Create Date: 2026-08-28 19:43:25.577978
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_assignment_completion_rollout"
down_revision: str | None = "0008_training_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Канонічний ідентифікатор Slice 4 довший за стандартний ліміт Alembic у 32 символи.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.add_column(
        "organization_memberships",
        sa.Column(
            "training_participation_status",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_training_participation_allowed"),
        "organization_memberships",
        "training_participation_status IN ('active', 'paused')",
    )
    op.create_unique_constraint(
        "uq_employee_profiles_id_organization_id",
        "employee_profiles",
        ["id", "organization_id"],
    )
    op.create_unique_constraint(
        "uq_lesson_versions_lesson_scope", "lesson_versions", ["id", "lesson_id"]
    )
    op.create_unique_constraint(
        "uq_training_versions_audience_scope",
        "training_versions",
        ["id", "organization_id", "location_id"],
    )
    op.create_table(
        "training_rollouts",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("from_version_id", sa.UUID(), nullable=False),
        sa.Column("to_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_assignment_set_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("from_version_revision", sa.Integer(), nullable=False),
        sa.Column("to_version_revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("previewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND previewed_at IS NULL AND confirmed_at IS NULL "
            "AND processing_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'preview_ready' AND previewed_at IS NOT NULL "
            "AND confirmed_at IS NULL AND processing_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'confirmed' AND previewed_at IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL AND processing_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'processing' AND previewed_at IS NOT NULL "
            "AND confirmed_at IS NOT NULL AND confirmed_by_user_id IS NOT NULL "
            "AND processing_at IS NOT NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND previewed_at IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL AND processing_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'failed' AND failure_code IS NOT NULL) OR "
            "(status = 'cancelled' AND completed_at IS NULL) OR "
            "(status = 'stale' AND previewed_at IS NOT NULL AND completed_at IS NULL)",
            name=op.f("ck_training_rollouts_lifecycle_timestamps_match"),
        ),
        sa.CheckConstraint(
            "(status = 'failed' AND failure_code IS NOT NULL) OR "
            "(status <> 'failed' AND failure_code IS NULL)",
            name=op.f("ck_training_rollouts_failure_code_matches"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'preview_ready', 'confirmed', 'processing', 'completed', "
            "'failed', 'cancelled', 'stale')",
            name=op.f("ck_training_rollouts_status_allowed"),
        ),
        sa.CheckConstraint(
            "from_version_id <> to_version_id", name=op.f("ck_training_rollouts_versions_differ")
        ),
        sa.CheckConstraint(
            "from_version_revision >= 0 AND to_version_revision >= 0",
            name=op.f("ck_training_rollouts_version_revisions_nonnegative"),
        ),
        sa.CheckConstraint("revision >= 0", name=op.f("ck_training_rollouts_revision_nonnegative")),
        sa.CheckConstraint(
            "source_assignment_set_fingerprint IS NULL OR "
            "length(source_assignment_set_fingerprint) = 64",
            name=op.f("ck_training_rollouts_source_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_training_rollouts_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_training_rollouts_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_version_id", "training_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.training_id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_rollouts_from_version_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_version_id", "training_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.training_id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_rollouts_to_version_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_training_rollouts_training_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_rollouts")),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_training_rollouts_lineage_scope",
        ),
    )
    op.create_index(
        "ix_training_rollouts_training_status_versions",
        "training_rollouts",
        ["training_id", "status", "from_version_id", "to_version_id"],
        unique=False,
    )
    op.create_index(
        "uq_training_rollouts_active_pair",
        "training_rollouts",
        ["training_id", "from_version_id", "to_version_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'preview_ready', 'confirmed', 'processing')"),
    )
    op.create_table(
        "training_version_audiences",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_version_id", sa.UUID(), nullable=False),
        sa.Column("operational_role_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_training_version_audiences_location_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            name="fk_training_version_audiences_role_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_version_audiences_version_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_version_audiences")),
        sa.UniqueConstraint(
            "training_version_id",
            "operational_role_id",
            name="uq_training_version_audiences_version_role",
        ),
    )
    op.create_index(
        "ix_training_version_audiences_role",
        "training_version_audiences",
        ["operational_role_id"],
        unique=False,
    )
    op.create_table(
        "training_assignments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column("training_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'assigned'"), nullable=False
        ),
        sa.Column(
            "source", sa.String(length=16), server_default=sa.text("'automatic'"), nullable=False
        ),
        sa.Column("previous_assignment_id", sa.UUID(), nullable=True),
        sa.Column("source_rollout_id", sa.UUID(), nullable=True),
        sa.Column("assigned_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=32), nullable=True),
        sa.Column("revoke_note", sa.String(length=500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'assigned' AND started_at IS NULL AND completed_at IS NULL "
            "AND revoked_at IS NULL AND revoke_reason IS NULL AND revoke_note IS NULL) OR "
            "(status = 'in_progress' AND started_at IS NOT NULL AND completed_at IS NULL "
            "AND revoked_at IS NULL AND revoke_reason IS NULL AND revoke_note IS NULL) OR "
            "(status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL "
            "AND revoked_at IS NULL AND revoke_reason IS NULL AND revoke_note IS NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name=op.f("ck_training_assignments_lifecycle_timestamps_match"),
        ),
        sa.CheckConstraint(
            "revoke_reason IS NULL OR revoke_reason IN "
            "('admin', 'role_changed', 'location_changed', 'rollout')",
            name=op.f("ck_training_assignments_revoke_reason_allowed"),
        ),
        sa.CheckConstraint(
            "source IN ('automatic', 'admin', 'reassign', 'rollout')",
            name=op.f("ck_training_assignments_source_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed', 'revoked')",
            name=op.f("ck_training_assignments_status_allowed"),
        ),
        sa.CheckConstraint(
            "revoke_note IS NULL OR length(revoke_note) BETWEEN 1 AND 500",
            name=op.f("ck_training_assignments_revoke_note_length"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name=op.f("fk_training_assignments_assigned_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_training_assignments_employee_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_training_assignments_location_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_assignment_id", "employee_profile_id", "training_id"],
            [
                "training_assignments.id",
                "training_assignments.employee_profile_id",
                "training_assignments.training_id",
            ],
            name="fk_training_assignments_previous_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_rollout_id", "organization_id", "location_id", "training_id"],
            [
                "training_rollouts.id",
                "training_rollouts.organization_id",
                "training_rollouts.location_id",
                "training_rollouts.training_id",
            ],
            name="fk_training_assignments_rollout_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_training_assignments_training_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_version_id", "training_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.training_id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_assignments_version_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_assignments")),
        sa.UniqueConstraint(
            "id", "employee_profile_id", "training_id", name="uq_training_assignments_lineage_scope"
        ),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_training_assignments_scope",
        ),
    )
    op.create_index(
        "ix_training_assignments_employee_assigned_at",
        "training_assignments",
        ["employee_profile_id", "assigned_at"],
        unique=False,
    )
    op.create_index(
        "ix_training_assignments_employee_training_status",
        "training_assignments",
        ["employee_profile_id", "training_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_training_assignments_current",
        "training_assignments",
        ["employee_profile_id", "training_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'revoked'"),
    )
    op.create_table(
        "lesson_completions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("lesson_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "completion_source",
            sa.String(length=32),
            server_default=sa.text("'employee'"),
            nullable=False,
        ),
        sa.Column("source_completion_id", sa.UUID(), nullable=True),
        sa.Column("source_rollout_id", sa.UUID(), nullable=True),
        sa.Column("completed_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(completion_source = 'employee' AND completed_by_user_id IS NOT NULL "
            "AND source_completion_id IS NULL AND source_rollout_id IS NULL) OR "
            "(completion_source = 'rollout_preserved' AND completed_by_user_id IS NULL "
            "AND source_completion_id IS NOT NULL AND source_rollout_id IS NOT NULL) OR "
            "(completion_source = 'reassignment_preserved' AND completed_by_user_id IS NULL "
            "AND source_completion_id IS NOT NULL AND source_rollout_id IS NULL)",
            name=op.f("ck_lesson_completions_source_provenance_match"),
        ),
        sa.CheckConstraint(
            "completion_source IN ('employee', 'rollout_preserved', 'reassignment_preserved')",
            name=op.f("ck_lesson_completions_completion_source_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "organization_id", "location_id", "training_id"],
            [
                "training_assignments.id",
                "training_assignments.organization_id",
                "training_assignments.location_id",
                "training_assignments.training_id",
            ],
            name="fk_lesson_completions_assignment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_user_id"],
            ["users.id"],
            name=op.f("fk_lesson_completions_completed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_lesson_completions_lesson_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_completion_id", "organization_id", "location_id", "training_id"],
            [
                "lesson_completions.id",
                "lesson_completions.organization_id",
                "lesson_completions.location_id",
                "lesson_completions.training_id",
            ],
            name="fk_lesson_completions_source_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_rollout_id", "organization_id", "location_id", "training_id"],
            [
                "training_rollouts.id",
                "training_rollouts.organization_id",
                "training_rollouts.location_id",
                "training_rollouts.training_id",
            ],
            name="fk_lesson_completions_rollout_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_completions")),
        sa.UniqueConstraint(
            "assignment_id", "lesson_id", name="uq_lesson_completions_assignment_lesson"
        ),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_lesson_completions_source_scope",
        ),
    )
    op.create_index(
        "ix_lesson_completions_assignment_lesson",
        "lesson_completions",
        ["assignment_id", "lesson_id"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_completions_source_completion",
        "lesson_completions",
        ["source_completion_id"],
        unique=False,
    )
    op.create_table(
        "rollout_employee_impacts",
        sa.Column("rollout_id", sa.UUID(), nullable=False),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_assignment_id", sa.UUID(), nullable=False),
        sa.Column("target_assignment_id", sa.UUID(), nullable=True),
        sa.Column("current_required_count", sa.Integer(), nullable=False),
        sa.Column("current_completed_count", sa.Integer(), nullable=False),
        sa.Column("current_progress_percentage", sa.Integer(), nullable=False),
        sa.Column("projected_required_count", sa.Integer(), nullable=False),
        sa.Column("projected_completed_count", sa.Integer(), nullable=False),
        sa.Column("projected_progress_percentage", sa.Integer(), nullable=False),
        sa.Column("lesson_impact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warning_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preview_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("previewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(lesson_impact) = 'object' "
            "AND lesson_impact ?& ARRAY['preserved', 'repeat', 'new', 'removed'] "
            "AND jsonb_typeof(lesson_impact->'preserved') = 'array' "
            "AND jsonb_typeof(lesson_impact->'repeat') = 'array' "
            "AND jsonb_typeof(lesson_impact->'new') = 'array' "
            "AND jsonb_typeof(lesson_impact->'removed') = 'array' "
            "AND jsonb_array_length(lesson_impact->'preserved') "
            "+ jsonb_array_length(lesson_impact->'repeat') "
            "+ jsonb_array_length(lesson_impact->'new') "
            "+ jsonb_array_length(lesson_impact->'removed') <= 1000 "
            "AND jsonb_typeof(validation_codes) = 'array' "
            "AND jsonb_array_length(validation_codes) <= 50 "
            "AND jsonb_typeof(warning_codes) = 'array' "
            "AND jsonb_array_length(warning_codes) <= 50",
            name=op.f("ck_rollout_employee_impacts_payload_shapes"),
        ),
        sa.CheckConstraint(
            "current_progress_percentage BETWEEN 0 AND 100 "
            "AND projected_progress_percentage BETWEEN 0 AND 100",
            name=op.f("ck_rollout_employee_impacts_progress_range"),
        ),
        sa.CheckConstraint(
            "current_required_count >= 0 AND current_completed_count >= 0 "
            "AND projected_required_count >= 0 AND projected_completed_count >= 0 "
            "AND current_completed_count <= current_required_count "
            "AND projected_completed_count <= projected_required_count",
            name=op.f("ck_rollout_employee_impacts_counts_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(preview_fingerprint) = 64",
            name=op.f("ck_rollout_employee_impacts_preview_fingerprint_length"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_profile_id"],
            ["employee_profiles.id"],
            name="fk_rollout_employee_impacts_employee",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rollout_id"],
            ["training_rollouts.id"],
            name="fk_rollout_employee_impacts_rollout",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_assignment_id"],
            ["training_assignments.id"],
            name="fk_rollout_employee_impacts_source_assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_assignment_id"],
            ["training_assignments.id"],
            name="fk_rollout_employee_impacts_target_assignment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rollout_employee_impacts")),
        sa.UniqueConstraint(
            "rollout_id",
            "source_assignment_id",
            name="uq_rollout_employee_impacts_rollout_assignment",
        ),
    )
    op.create_index(
        "ix_rollout_employee_impacts_rollout_employee",
        "rollout_employee_impacts",
        ["rollout_id", "employee_profile_id"],
        unique=False,
    )
    op.create_table(
        "rollout_lesson_rules",
        sa.Column("rollout_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("from_lesson_version_id", sa.UUID(), nullable=True),
        sa.Column("to_lesson_version_id", sa.UUID(), nullable=True),
        sa.Column("rule", sa.String(length=32), nullable=True),
        sa.Column("requires_admin_decision", sa.Boolean(), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(requires_admin_decision = false AND rule IS NOT NULL "
            "AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(requires_admin_decision = true AND rule IS NULL "
            "AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(requires_admin_decision = true "
            "AND rule IN ('preserve_completion', 'needs_repeat') "
            "AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)",
            name=op.f("ck_rollout_lesson_rules_decision_matches"),
        ),
        sa.CheckConstraint(
            "(rule = 'new_incomplete' AND from_lesson_version_id IS NULL "
            "AND to_lesson_version_id IS NOT NULL) OR "
            "(rule = 'removed_historical' AND from_lesson_version_id IS NOT NULL "
            "AND to_lesson_version_id IS NULL) OR "
            "((rule IS NULL OR rule IN ('preserve_completion', 'needs_repeat')) "
            "AND from_lesson_version_id IS NOT NULL AND to_lesson_version_id IS NOT NULL)",
            name=op.f("ck_rollout_lesson_rules_versions_match_rule"),
        ),
        sa.CheckConstraint(
            "rule IS NULL OR rule IN ('preserve_completion', 'needs_repeat', "
            "'new_incomplete', 'removed_historical')",
            name=op.f("ck_rollout_lesson_rules_rule_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_rollout_lesson_rules_decided_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_rollout_lesson_rules_from_lesson_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rollout_id"],
            ["training_rollouts.id"],
            name="fk_rollout_lesson_rules_rollout",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_rollout_lesson_rules_to_lesson_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rollout_lesson_rules")),
        sa.UniqueConstraint(
            "rollout_id", "lesson_id", name="uq_rollout_lesson_rules_rollout_lesson"
        ),
    )
    op.create_index(
        "ix_rollout_lesson_rules_rollout_lesson",
        "rollout_lesson_rules",
        ["rollout_id", "lesson_id"],
        unique=False,
    )
    op.drop_constraint(
        op.f("ck_background_jobs_job_type_allowed"), "background_jobs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_job_type_allowed"),
        "background_jobs",
        "job_type IN ('invitation_email', 'training_assignment_notification', "
        "'training_rollout_notification')",
    )
    op.drop_constraint(
        op.f("ck_background_jobs_invitation_payload_required"), "background_jobs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"),
        "background_jobs",
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
        "= '{}'::jsonb))",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"), "background_jobs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_invitation_payload_required"),
        "background_jobs",
        "jsonb_typeof(payload) = 'object'::text "
        "AND payload ? 'invitation_id'::text AND payload ? 'token_version'::text",
    )
    op.drop_constraint(
        op.f("ck_background_jobs_job_type_allowed"), "background_jobs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_job_type_allowed"),
        "background_jobs",
        "job_type = 'invitation_email'",
    )
    op.drop_index("ix_rollout_lesson_rules_rollout_lesson", table_name="rollout_lesson_rules")
    op.drop_table("rollout_lesson_rules")
    op.drop_index(
        "ix_rollout_employee_impacts_rollout_employee", table_name="rollout_employee_impacts"
    )
    op.drop_table("rollout_employee_impacts")
    op.drop_index("ix_lesson_completions_source_completion", table_name="lesson_completions")
    op.drop_index("ix_lesson_completions_assignment_lesson", table_name="lesson_completions")
    op.drop_table("lesson_completions")
    op.drop_index(
        "uq_training_assignments_current",
        table_name="training_assignments",
        postgresql_where=sa.text("status <> 'revoked'"),
    )
    op.drop_index(
        "ix_training_assignments_employee_training_status", table_name="training_assignments"
    )
    op.drop_index("ix_training_assignments_employee_assigned_at", table_name="training_assignments")
    op.drop_table("training_assignments")
    op.drop_index("ix_training_version_audiences_role", table_name="training_version_audiences")
    op.drop_table("training_version_audiences")
    op.drop_index(
        "uq_training_rollouts_active_pair",
        table_name="training_rollouts",
        postgresql_where=sa.text("status IN ('draft', 'preview_ready', 'confirmed', 'processing')"),
    )
    op.drop_index("ix_training_rollouts_training_status_versions", table_name="training_rollouts")
    op.drop_table("training_rollouts")
    op.drop_constraint("uq_training_versions_audience_scope", "training_versions", type_="unique")
    op.drop_constraint("uq_lesson_versions_lesson_scope", "lesson_versions", type_="unique")
    op.drop_constraint(
        "uq_employee_profiles_id_organization_id", "employee_profiles", type_="unique"
    )
    # Дозволяє локально відкотити як первісну, так і уточнену ревізію 0009.
    op.execute(
        sa.text(
            "ALTER TABLE organization_memberships DROP CONSTRAINT IF EXISTS "
            "ck_organization_memberships_training_participation_allowed"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE organization_memberships DROP COLUMN IF EXISTS "
            "training_participation_status"
        )
    )
