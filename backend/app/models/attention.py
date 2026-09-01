from datetime import datetime
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
    AttentionCaseState,
    AttentionCaseType,
    RetakeRequirementReason,
    RetakeRequirementState,
)


def _uuid() -> PostgreSQLUUID[UUID]:
    return PostgreSQLUUID(as_uuid=True)


class CriticalError(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "critical_errors"
    __table_args__ = (
        UniqueConstraint("submitted_answer_id", name="uq_critical_errors_source_answer"),
        UniqueConstraint("id", "organization_id", "location_id", name="uq_critical_errors_scope"),
        CheckConstraint("critical_type = 'allergen'", name="critical_type_allergen"),
        CheckConstraint("length(btrim(subject_key)) BETWEEN 1 AND 200", name="subject_key_length"),
        CheckConstraint("jsonb_typeof(safe_context) = 'object'", name="safe_context_object"),
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_critical_errors_employee_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "attempt_id",
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
            name="fk_critical_errors_attempt_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["attempt_question_id", "attempt_id"],
            ["attempt_questions.id", "attempt_questions.attempt_id"],
            name="fk_critical_errors_question_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["submitted_answer_id", "attempt_id", "attempt_question_id"],
            [
                "submitted_answers.id",
                "submitted_answers.attempt_id",
                "submitted_answers.attempt_question_id",
            ],
            name="fk_critical_errors_answer_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["menu_item_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_items.id",
                "menu_items.menu_id",
                "menu_items.organization_id",
                "menu_items.location_id",
            ],
            name="fk_critical_errors_menu_item_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_critical_errors_employee_subject",
            "organization_id",
            "employee_profile_id",
            "training_id",
            "subject_key",
            "occurred_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    attempt_question_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    submitted_answer_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_item_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    allergen_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("allergens.id", ondelete="RESTRICT"), nullable=False
    )
    critical_type: Mapped[str] = mapped_column(String(32), nullable=False, default="allergen")
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    safe_context: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AttentionCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attention_cases"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "location_id", name="uq_attention_cases_scope"),
        CheckConstraint(
            "case_type IN ('critical_allergen', 'retake_overdue')", name="type_allowed"
        ),
        CheckConstraint("state IN ('open', 'acknowledged', 'resolved')", name="state_allowed"),
        CheckConstraint(
            "(case_type = 'critical_allergen' AND subject_key IS NOT NULL) OR "
            "(case_type = 'retake_overdue' AND subject_key IS NULL)",
            name="subject_matches_type",
        ),
        CheckConstraint(
            "subject_key IS NULL OR length(btrim(subject_key)) BETWEEN 1 AND 200",
            name="subject_key_length",
        ),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint(
            "(state = 'open' AND acknowledged_at IS NULL AND resolved_at IS NULL "
            "AND resolution_type IS NULL AND resolution_actor_type IS NULL "
            "AND resolved_by_user_id IS NULL AND resolution_comment IS NULL) OR "
            "(state = 'acknowledged' AND acknowledged_at IS NOT NULL "
            "AND acknowledged_by_user_id IS NOT NULL AND resolved_at IS NULL "
            "AND resolution_type IS NULL AND resolution_actor_type IS NULL "
            "AND resolved_by_user_id IS NULL AND resolution_comment IS NULL) OR "
            "(state = 'resolved' AND resolved_at IS NOT NULL "
            "AND resolution_type IS NOT NULL AND resolution_actor_type IN ('user', 'system') "
            "AND ((resolution_actor_type = 'user' AND resolved_by_user_id IS NOT NULL) "
            "OR (resolution_actor_type = 'system' AND resolved_by_user_id IS NULL)))",
            name="lifecycle_fields_match",
        ),
        CheckConstraint(
            "resolution_type IS NULL OR resolution_type IN "
            "('clean_retake', 'admin_follow_up', 'requirement_completed', "
            "'requirement_cancelled')",
            name="resolution_type_allowed",
        ),
        CheckConstraint(
            "resolution_comment IS NULL OR length(btrim(resolution_comment)) BETWEEN 1 AND 500",
            name="resolution_comment_length",
        ),
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_attention_cases_employee_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_attention_cases_training_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_attention_cases_unresolved_critical",
            "organization_id",
            "employee_profile_id",
            "training_id",
            "case_type",
            "subject_key",
            unique=True,
            postgresql_where=text(
                "case_type = 'critical_allergen' AND state IN ('open', 'acknowledged')"
            ),
        ),
        Index(
            "ix_attention_cases_admin_queue",
            "organization_id",
            "state",
            "case_type",
            "created_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    case_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AttentionCaseType.CRITICAL_ALLERGEN.value
    )
    subject_key: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AttentionCaseState.OPEN.value, server_default="open"
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    acknowledged_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_type: Mapped[str | None] = mapped_column(String(32))
    resolution_actor_type: Mapped[str | None] = mapped_column(String(16))
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_comment: Mapped[str | None] = mapped_column(String(500))


class RetakeRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retake_requirements"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_retake_requirements_scope"
        ),
        CheckConstraint(
            "reason IN ('failed_exam', 'critical_error', 'management_follow_up', "
            "'material_content_change')",
            name="reason_allowed",
        ),
        CheckConstraint(
            "state IN ('proposed', 'active', 'completed', 'cancelled')",
            name="state_allowed",
        ),
        CheckConstraint("jsonb_typeof(target_policy) = 'object'", name="target_policy_object"),
        CheckConstraint("frozen_seconds >= 0", name="frozen_seconds_nonnegative"),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint(
            "(state = 'proposed' AND proposed_at IS NOT NULL "
            "AND proposed_by_user_id IS NOT NULL AND confirmed_at IS NULL) OR "
            "(state IN ('active', 'completed') AND confirmed_at IS NOT NULL) OR "
            "(state = 'cancelled')",
            name="activation_fields_match",
        ),
        CheckConstraint(
            "(state = 'completed' AND completed_at IS NOT NULL "
            "AND completion_attempt_id IS NOT NULL AND cancelled_at IS NULL "
            "AND cancelled_by_user_id IS NULL AND cancellation_comment IS NULL) OR "
            "(state = 'cancelled' AND completed_at IS NULL "
            "AND completion_attempt_id IS NULL AND cancelled_at IS NOT NULL "
            "AND cancelled_by_user_id IS NOT NULL "
            "AND length(btrim(cancellation_comment)) BETWEEN 1 AND 500) OR "
            "(state IN ('proposed', 'active') AND completed_at IS NULL "
            "AND completion_attempt_id IS NULL AND cancelled_at IS NULL "
            "AND cancelled_by_user_id IS NULL AND cancellation_comment IS NULL)",
            name="terminal_state_match",
        ),
        CheckConstraint(
            "(reason = 'failed_exam' AND source_result_id IS NOT NULL "
            "AND source_attempt_id IS NOT NULL AND source_attention_case_id IS NULL "
            "AND management_source_key IS NULL) OR "
            "(reason = 'critical_error' AND source_result_id IS NULL "
            "AND source_attempt_id IS NULL AND source_attention_case_id IS NOT NULL "
            "AND management_source_key IS NULL) OR "
            "(reason IN ('management_follow_up', 'material_content_change') "
            "AND source_result_id IS NULL AND source_attempt_id IS NULL "
            "AND source_attention_case_id IS NULL "
            "AND length(btrim(management_source_key)) BETWEEN 1 AND 200)",
            name="source_matches_reason",
        ),
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_retake_requirements_employee_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "location_id", "training_id"],
            [
                "training_assignments.id",
                "training_assignments.organization_id",
                "training_assignments.location_id",
                "training_assignments.training_id",
            ],
            name="fk_retake_requirements_assignment_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_assessment_id", "organization_id", "location_id", "training_id"],
            [
                "assessments.id",
                "assessments.organization_id",
                "assessments.location_id",
                "assessments.training_id",
            ],
            name="fk_retake_requirements_target_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_result_id", "source_attempt_id"],
            ["attempt_results.id", "attempt_results.attempt_id"],
            name="fk_retake_requirements_source_result",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "source_attempt_id",
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
            name="fk_retake_requirements_source_attempt_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_attention_case_id", "organization_id", "location_id"],
            [
                "attention_cases.id",
                "attention_cases.organization_id",
                "attention_cases.location_id",
            ],
            name="fk_retake_requirements_attention_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "completion_attempt_id",
                "employee_profile_id",
                "organization_id",
                "location_id",
                "training_id",
            ],
            [
                "assessment_attempts.id",
                "assessment_attempts.employee_profile_id",
                "assessment_attempts.organization_id",
                "assessment_attempts.location_id",
                "assessment_attempts.training_id",
            ],
            name="fk_retake_requirements_completion_attempt",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_retake_requirements_failed_current",
            "employee_profile_id",
            "training_id",
            "target_assessment_id",
            unique=True,
            postgresql_where=text("reason = 'failed_exam' AND state IN ('proposed', 'active')"),
        ),
        Index(
            "uq_retake_requirements_critical_current",
            "source_attention_case_id",
            unique=True,
            postgresql_where=text("reason = 'critical_error' AND state IN ('proposed', 'active')"),
        ),
        Index(
            "uq_retake_requirements_management_current",
            "employee_profile_id",
            "target_assessment_id",
            "management_source_key",
            unique=True,
            postgresql_where=text(
                "reason = 'management_follow_up' AND state IN ('proposed', 'active')"
            ),
        ),
        Index(
            "uq_retake_requirements_failed_source",
            "source_result_id",
            unique=True,
            postgresql_where=text("reason = 'failed_exam'"),
        ),
        Index(
            "ix_retake_requirements_admin_due",
            "organization_id",
            "state",
            "due_at",
        ),
        Index(
            "ix_retake_requirements_employee_current",
            "employee_profile_id",
            "state",
            "due_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    target_assessment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    reason: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RetakeRequirementReason.FAILED_EXAM.value
    )
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RetakeRequirementState.PROPOSED.value
    )
    source_result_id: Mapped[UUID | None] = mapped_column(_uuid())
    source_attempt_id: Mapped[UUID | None] = mapped_column(_uuid())
    source_attention_case_id: Mapped[UUID | None] = mapped_column(_uuid())
    management_source_key: Mapped[str | None] = mapped_column(String(200))
    target_policy: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposed_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    frozen_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_attempt_id: Mapped[UUID | None] = mapped_column(_uuid())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    cancellation_comment: Mapped[str | None] = mapped_column(String(500))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class AttentionCaseSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attention_case_sources"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(critical_error_id, retake_requirement_id) = 1",
            name="exactly_one_source",
        ),
        ForeignKeyConstraint(
            ["attention_case_id", "organization_id", "location_id"],
            [
                "attention_cases.id",
                "attention_cases.organization_id",
                "attention_cases.location_id",
            ],
            name="fk_attention_case_sources_case_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["critical_error_id", "organization_id", "location_id"],
            [
                "critical_errors.id",
                "critical_errors.organization_id",
                "critical_errors.location_id",
            ],
            name="fk_attention_case_sources_critical_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["retake_requirement_id", "organization_id", "location_id"],
            [
                "retake_requirements.id",
                "retake_requirements.organization_id",
                "retake_requirements.location_id",
            ],
            name="fk_attention_case_sources_requirement_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_attention_case_sources_critical_error",
            "critical_error_id",
            unique=True,
            postgresql_where=text("critical_error_id IS NOT NULL"),
        ),
        Index(
            "uq_attention_case_sources_retake_requirement",
            "retake_requirement_id",
            unique=True,
            postgresql_where=text("retake_requirement_id IS NOT NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    attention_case_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    critical_error_id: Mapped[UUID | None] = mapped_column(_uuid())
    retake_requirement_id: Mapped[UUID | None] = mapped_column(_uuid())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AttentionCaseAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attention_case_actions"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system') "
            "AND ((actor_type = 'user' AND actor_user_id IS NOT NULL) "
            "OR (actor_type = 'system' AND actor_user_id IS NULL))",
            name="actor_matches_type",
        ),
        CheckConstraint(
            "action IN ('opened', 'source_added', 'acknowledged', "
            "'requirement_linked', 'resolved')",
            name="action_allowed",
        ),
        CheckConstraint(
            "from_state IS NULL OR from_state IN ('open', 'acknowledged', 'resolved')",
            name="from_state_allowed",
        ),
        CheckConstraint(
            "to_state IS NULL OR to_state IN ('open', 'acknowledged', 'resolved')",
            name="to_state_allowed",
        ),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) BETWEEN 1 AND 500",
            name="comment_length",
        ),
        ForeignKeyConstraint(
            ["attention_case_id", "organization_id", "location_id"],
            [
                "attention_cases.id",
                "attention_cases.organization_id",
                "attention_cases.location_id",
            ],
            name="fk_attention_case_actions_case_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_attention_case_actions_history", "attention_case_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    attention_case_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str | None] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RetakeRequirementAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retake_requirement_actions"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system') "
            "AND ((actor_type = 'user' AND actor_user_id IS NOT NULL) "
            "OR (actor_type = 'system' AND actor_user_id IS NULL))",
            name="actor_matches_type",
        ),
        CheckConstraint(
            "action IN ('proposed', 'confirmed', 'attempt_observed', 'frozen', "
            "'resumed', 'completed', 'cancelled', 'deadline_projected')",
            name="action_allowed",
        ),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) BETWEEN 1 AND 500",
            name="comment_length",
        ),
        ForeignKeyConstraint(
            ["retake_requirement_id", "organization_id", "location_id"],
            [
                "retake_requirements.id",
                "retake_requirements.organization_id",
                "retake_requirements.location_id",
            ],
            name="fk_retake_requirement_actions_requirement_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_retake_requirement_actions_history", "retake_requirement_id", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    retake_requirement_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("assessment_attempts.id", ondelete="RESTRICT")
    )
    comment: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
