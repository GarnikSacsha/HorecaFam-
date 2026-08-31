"""Add Practice assessment persistence and durable eligibility.

Revision ID: 0014_practice_persistence
Revises: 0013_question_templates
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_practice_persistence"
down_revision: str | None = "0013_question_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("assessments", "lesson_id", existing_type=sa.UUID(), nullable=True)
    op.create_unique_constraint(
        "uq_assessments_training_scope",
        "assessments",
        ["id", "organization_id", "location_id", "training_id"],
    )
    op.create_check_constraint(
        "scope_matches_type",
        "assessments",
        "(assessment_type = 'interactive_training' AND lesson_id IS NOT NULL) OR "
        "(assessment_type IN ('whole_menu_knowledge_check', 'menu_final_exam') "
        "AND lesson_id IS NULL)",
    )
    op.create_index(
        "uq_assessments_training_type",
        "assessments",
        ["training_id", "assessment_type"],
        unique=True,
        postgresql_where=sa.text("lesson_id IS NULL"),
    )

    op.drop_constraint(
        op.f("ck_assessment_versions_interactive_feedback_policy"),
        "assessment_versions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_assessment_versions_interactive_question_count"),
        "assessment_versions",
        type_="check",
    )
    op.alter_column("assessment_versions", "lesson_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column(
        "assessment_versions", "lesson_version_id", existing_type=sa.UUID(), nullable=True
    )
    op.alter_column(
        "assessment_versions",
        "feedback_policy",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default="immediate",
    )
    op.add_column("assessment_versions", sa.Column("threshold_percent", sa.Integer()))
    op.create_check_constraint(
        "configuration_matches_scope",
        "assessment_versions",
        "(lesson_id IS NOT NULL AND lesson_version_id IS NOT NULL "
        "AND question_count = 5 AND threshold_percent IS NULL "
        "AND feedback_policy = 'immediate') OR "
        "(lesson_id IS NULL AND lesson_version_id IS NULL "
        "AND ((question_count = 10 AND threshold_percent = 40) "
        "OR (question_count = 20 AND threshold_percent = 70)) "
        "AND feedback_policy = 'after_final_submission')",
    )

    op.drop_constraint(
        op.f("ck_assessment_readiness_counts_valid"), "assessment_readiness", type_="check"
    )
    op.create_check_constraint(
        "counts_valid",
        "assessment_readiness",
        "eligible_count >= 0 AND required_count IN (5, 10, 20)",
    )

    op.create_unique_constraint(
        "uq_assessment_attempts_eligibility_scope",
        "assessment_attempts",
        [
            "id",
            "employee_profile_id",
            "assignment_id",
            "organization_id",
            "location_id",
            "training_id",
        ],
    )
    op.drop_constraint(
        op.f("ck_assessment_attempts_question_count_five"),
        "assessment_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "question_count_allowed",
        "assessment_attempts",
        "question_count IN (5, 10, 20)",
    )

    op.drop_constraint(
        op.f("ck_attempt_questions_position_range"), "attempt_questions", type_="check"
    )
    op.create_check_constraint("position_range", "attempt_questions", "position BETWEEN 0 AND 19")

    op.drop_constraint(
        op.f("ck_attempt_results_interactive_pass_status_null"),
        "attempt_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_attempt_results_total_count_five"), "attempt_results", type_="check"
    )
    op.create_check_constraint(
        "total_count_allowed", "attempt_results", "total_count IN (5, 10, 20)"
    )
    op.create_check_constraint(
        "pass_status_matches_count",
        "attempt_results",
        "(total_count IN (5, 10) AND pass_status IS NULL) OR "
        "(total_count = 20 AND pass_status IN ('passed', 'failed'))",
    )

    op.create_table(
        "assessment_eligibilities",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("target_assessment_id", sa.UUID(), nullable=False),
        sa.Column("earned_by_attempt_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="earned", nullable=False),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True)),
        sa.Column("reset_by_user_id", sa.UUID()),
        sa.Column("reset_reason", sa.String(length=500)),
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
            "status IN ('earned', 'reset')",
            name=op.f("ck_assessment_eligibilities_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'earned' AND reset_at IS NULL AND reset_by_user_id IS NULL "
            "AND reset_reason IS NULL) OR "
            "(status = 'reset' AND reset_at IS NOT NULL AND reset_by_user_id IS NOT NULL "
            "AND length(btrim(reset_reason)) BETWEEN 1 AND 500)",
            name=op.f("ck_assessment_eligibilities_status_timestamps_match"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_assessment_eligibilities_employee_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "organization_id", "location_id", "training_id"],
            [
                "training_assignments.id",
                "training_assignments.organization_id",
                "training_assignments.location_id",
                "training_assignments.training_id",
            ],
            name="fk_assessment_eligibilities_assignment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_assessment_id", "organization_id", "location_id", "training_id"],
            [
                "assessments.id",
                "assessments.organization_id",
                "assessments.location_id",
                "assessments.training_id",
            ],
            name="fk_assessment_eligibilities_target_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "earned_by_attempt_id",
                "employee_profile_id",
                "assignment_id",
                "organization_id",
                "location_id",
                "training_id",
            ],
            [
                "assessment_attempts.id",
                "assessment_attempts.employee_profile_id",
                "assessment_attempts.assignment_id",
                "assessment_attempts.organization_id",
                "assessment_attempts.location_id",
                "assessment_attempts.training_id",
            ],
            name="fk_assessment_eligibilities_attempt_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reset_by_user_id"],
            ["users.id"],
            name=op.f("fk_assessment_eligibilities_reset_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_eligibilities")),
        sa.UniqueConstraint(
            "earned_by_attempt_id", name="uq_assessment_eligibilities_earned_attempt"
        ),
    )
    op.create_index(
        "uq_assessment_eligibilities_active",
        "assessment_eligibilities",
        ["employee_profile_id", "assignment_id", "target_assessment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'earned'"),
    )
    op.create_index(
        "ix_assessment_eligibilities_employee_history",
        "assessment_eligibilities",
        ["employee_profile_id", "target_assessment_id", "earned_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assessment_eligibilities_employee_history",
        table_name="assessment_eligibilities",
    )
    op.drop_index("uq_assessment_eligibilities_active", table_name="assessment_eligibilities")
    op.drop_table("assessment_eligibilities")

    op.drop_constraint(
        op.f("ck_attempt_results_pass_status_matches_count"),
        "attempt_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_attempt_results_total_count_allowed"), "attempt_results", type_="check"
    )
    op.create_check_constraint(
        "interactive_pass_status_null", "attempt_results", "pass_status IS NULL"
    )
    op.create_check_constraint("total_count_five", "attempt_results", "total_count = 5")

    op.drop_constraint(
        op.f("ck_attempt_questions_position_range"), "attempt_questions", type_="check"
    )
    op.create_check_constraint("position_range", "attempt_questions", "position BETWEEN 0 AND 4")

    op.drop_constraint(
        op.f("ck_assessment_attempts_question_count_allowed"),
        "assessment_attempts",
        type_="check",
    )
    op.create_check_constraint("question_count_five", "assessment_attempts", "question_count = 5")
    op.drop_constraint(
        "uq_assessment_attempts_eligibility_scope", "assessment_attempts", type_="unique"
    )

    op.drop_constraint(
        op.f("ck_assessment_readiness_counts_valid"), "assessment_readiness", type_="check"
    )
    op.create_check_constraint(
        "counts_valid",
        "assessment_readiness",
        "eligible_count >= 0 AND required_count = 5",
    )

    op.drop_constraint(
        op.f("ck_assessment_versions_configuration_matches_scope"),
        "assessment_versions",
        type_="check",
    )
    op.drop_column("assessment_versions", "threshold_percent")
    op.alter_column(
        "assessment_versions",
        "feedback_policy",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
        existing_server_default="immediate",
    )
    op.alter_column(
        "assessment_versions", "lesson_version_id", existing_type=sa.UUID(), nullable=False
    )
    op.alter_column("assessment_versions", "lesson_id", existing_type=sa.UUID(), nullable=False)
    op.create_check_constraint(
        "interactive_question_count", "assessment_versions", "question_count = 5"
    )
    op.create_check_constraint(
        "interactive_feedback_policy",
        "assessment_versions",
        "feedback_policy = 'immediate'",
    )

    op.drop_index("uq_assessments_training_type", table_name="assessments")
    op.drop_constraint(op.f("ck_assessments_scope_matches_type"), "assessments", type_="check")
    op.drop_constraint("uq_assessments_training_scope", "assessments", type_="unique")
    op.alter_column("assessments", "lesson_id", existing_type=sa.UUID(), nullable=False)
