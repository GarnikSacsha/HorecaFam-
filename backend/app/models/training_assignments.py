from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
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
    LessonCompletionSource,
    TrainingAssignmentSource,
    TrainingAssignmentStatus,
    TrainingRolloutStatus,
)


def _uuid() -> PostgreSQLUUID[UUID]:
    return PostgreSQLUUID(as_uuid=True)


class TrainingVersionAudience(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "training_version_audiences"
    __table_args__ = (
        UniqueConstraint(
            "training_version_id",
            "operational_role_id",
            name="uq_training_version_audiences_version_role",
        ),
        ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_version_audiences_version_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            name="fk_training_version_audiences_role_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_training_version_audiences_location_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_training_version_audiences_role", "operational_role_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    operational_role_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TrainingRollout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_rollouts"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_training_rollouts_lineage_scope",
        ),
        CheckConstraint(
            "status IN ('draft', 'preview_ready', 'confirmed', 'processing', 'completed', "
            "'failed', 'cancelled', 'stale')",
            name="status_allowed",
        ),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint(
            "from_version_revision >= 0 AND to_version_revision >= 0",
            name="version_revisions_nonnegative",
        ),
        CheckConstraint("from_version_id <> to_version_id", name="versions_differ"),
        CheckConstraint(
            "source_assignment_set_fingerprint IS NULL OR "
            "length(source_assignment_set_fingerprint) = 64",
            name="source_fingerprint_length",
        ),
        CheckConstraint(
            "(status = 'draft' AND previewed_at IS NULL AND confirmed_at IS NULL "
            "AND processing_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'preview_ready' AND previewed_at IS NOT NULL AND confirmed_at IS NULL "
            "AND processing_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'confirmed' AND previewed_at IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL AND processing_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'processing' AND previewed_at IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL AND processing_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'completed' AND previewed_at IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL AND processing_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'failed' AND failure_code IS NOT NULL) OR "
            "(status = 'cancelled' AND completed_at IS NULL) OR "
            "(status = 'stale' AND previewed_at IS NOT NULL AND completed_at IS NULL)",
            name="lifecycle_timestamps_match",
        ),
        CheckConstraint(
            "(status = 'failed' AND failure_code IS NOT NULL) OR "
            "(status <> 'failed' AND failure_code IS NULL)",
            name="failure_code_matches",
        ),
        ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_training_rollouts_training_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        Index(
            "uq_training_rollouts_active_pair",
            "training_id",
            "from_version_id",
            "to_version_id",
            unique=True,
            postgresql_where=text(
                "status IN ('draft', 'preview_ready', 'confirmed', 'processing')"
            ),
        ),
        Index(
            "ix_training_rollouts_training_status_versions",
            "training_id",
            "status",
            "from_version_id",
            "to_version_id",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    from_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    to_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingRolloutStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_assignment_set_fingerprint: Mapped[str | None] = mapped_column(String(64))
    from_version_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    previewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))


class TrainingAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_assignments"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_training_assignments_scope",
        ),
        UniqueConstraint(
            "id",
            "employee_profile_id",
            "training_id",
            name="uq_training_assignments_lineage_scope",
        ),
        CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed', 'revoked')",
            name="status_allowed",
        ),
        CheckConstraint(
            "source IN ('automatic', 'admin', 'reassign', 'rollout')",
            name="source_allowed",
        ),
        CheckConstraint(
            "revoke_reason IS NULL OR revoke_reason IN "
            "('admin', 'role_changed', 'location_changed', 'rollout')",
            name="revoke_reason_allowed",
        ),
        CheckConstraint(
            "revoke_note IS NULL OR length(revoke_note) BETWEEN 1 AND 500",
            name="revoke_note_length",
        ),
        CheckConstraint(
            "(status = 'assigned' AND started_at IS NULL AND completed_at IS NULL "
            "AND revoked_at IS NULL AND revoke_reason IS NULL AND revoke_note IS NULL) OR "
            "(status = 'in_progress' AND started_at IS NOT NULL AND completed_at IS NULL "
            "AND revoked_at IS NULL AND revoke_reason IS NULL AND revoke_note IS NULL) OR "
            "(status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL "
            "AND revoked_at IS NULL AND revoke_reason IS NULL AND revoke_note IS NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="lifecycle_timestamps_match",
        ),
        ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_training_assignments_training_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_training_assignments_employee_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_training_assignments_location_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["previous_assignment_id", "employee_profile_id", "training_id"],
            [
                "training_assignments.id",
                "training_assignments.employee_profile_id",
                "training_assignments.training_id",
            ],
            name="fk_training_assignments_previous_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        Index(
            "uq_training_assignments_current",
            "employee_profile_id",
            "training_id",
            unique=True,
            postgresql_where=text("status <> 'revoked'"),
        ),
        Index(
            "ix_training_assignments_employee_training_status",
            "employee_profile_id",
            "training_id",
            "status",
        ),
        Index(
            "ix_training_assignments_employee_assigned_at",
            "employee_profile_id",
            "assigned_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingAssignmentStatus.ASSIGNED.value,
        server_default=text("'assigned'"),
    )
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingAssignmentSource.AUTOMATIC.value,
        server_default=text("'automatic'"),
    )
    previous_assignment_id: Mapped[UUID | None] = mapped_column(_uuid())
    source_rollout_id: Mapped[UUID | None] = mapped_column(_uuid())
    assigned_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(32))
    revoke_note: Mapped[str | None] = mapped_column(String(500))


class LessonCompletion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lesson_completions"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "lesson_id", name="uq_lesson_completions_assignment_lesson"
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_lesson_completions_source_scope",
        ),
        CheckConstraint(
            "completion_source IN ('employee', 'rollout_preserved', 'reassignment_preserved')",
            name="completion_source_allowed",
        ),
        CheckConstraint(
            "(completion_source = 'employee' AND completed_by_user_id IS NOT NULL "
            "AND source_completion_id IS NULL AND source_rollout_id IS NULL) OR "
            "(completion_source = 'rollout_preserved' AND completed_by_user_id IS NULL "
            "AND source_completion_id IS NOT NULL AND source_rollout_id IS NOT NULL) OR "
            "(completion_source = 'reassignment_preserved' AND completed_by_user_id IS NULL "
            "AND source_completion_id IS NOT NULL AND source_rollout_id IS NULL)",
            name="source_provenance_match",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_lesson_completions_lesson_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        Index("ix_lesson_completions_assignment_lesson", "assignment_id", "lesson_id"),
        Index("ix_lesson_completions_source_completion", "source_completion_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    lesson_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    lesson_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    completion_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LessonCompletionSource.EMPLOYEE.value,
        server_default=text("'employee'"),
    )
    source_completion_id: Mapped[UUID | None] = mapped_column(_uuid())
    source_rollout_id: Mapped[UUID | None] = mapped_column(_uuid())
    completed_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RolloutLessonRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rollout_lesson_rules"
    __table_args__ = (
        UniqueConstraint("rollout_id", "lesson_id", name="uq_rollout_lesson_rules_rollout_lesson"),
        CheckConstraint(
            "rule IS NULL OR rule IN ('preserve_completion', 'needs_repeat', "
            "'new_incomplete', 'removed_historical')",
            name="rule_allowed",
        ),
        CheckConstraint(
            "(requires_admin_decision = false AND rule IS NOT NULL "
            "AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(requires_admin_decision = true AND rule IS NULL "
            "AND decided_by_user_id IS NULL AND decided_at IS NULL) OR "
            "(requires_admin_decision = true "
            "AND rule IN ('preserve_completion', 'needs_repeat') "
            "AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)",
            name="decision_matches",
        ),
        CheckConstraint(
            "(rule = 'new_incomplete' AND from_lesson_version_id IS NULL "
            "AND to_lesson_version_id IS NOT NULL) OR "
            "(rule = 'removed_historical' AND from_lesson_version_id IS NOT NULL "
            "AND to_lesson_version_id IS NULL) OR "
            "((rule IS NULL OR rule IN ('preserve_completion', 'needs_repeat')) "
            "AND from_lesson_version_id IS NOT NULL AND to_lesson_version_id IS NOT NULL)",
            name="versions_match_rule",
        ),
        ForeignKeyConstraint(
            ["rollout_id"],
            ["training_rollouts.id"],
            name="fk_rollout_lesson_rules_rollout",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["from_lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_rollout_lesson_rules_from_lesson_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["to_lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_rollout_lesson_rules_to_lesson_version",
            ondelete="RESTRICT",
        ),
        Index("ix_rollout_lesson_rules_rollout_lesson", "rollout_id", "lesson_id"),
    )

    rollout_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    lesson_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    from_lesson_version_id: Mapped[UUID | None] = mapped_column(_uuid())
    to_lesson_version_id: Mapped[UUID | None] = mapped_column(_uuid())
    rule: Mapped[str | None] = mapped_column(String(32))
    requires_admin_decision: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RolloutEmployeeImpact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rollout_employee_impacts"
    __table_args__ = (
        UniqueConstraint(
            "rollout_id",
            "source_assignment_id",
            name="uq_rollout_employee_impacts_rollout_assignment",
        ),
        CheckConstraint(
            "current_required_count >= 0 AND current_completed_count >= 0 "
            "AND projected_required_count >= 0 AND projected_completed_count >= 0 "
            "AND current_completed_count <= current_required_count "
            "AND projected_completed_count <= projected_required_count",
            name="counts_nonnegative",
        ),
        CheckConstraint(
            "current_progress_percentage BETWEEN 0 AND 100 "
            "AND projected_progress_percentage BETWEEN 0 AND 100",
            name="progress_range",
        ),
        CheckConstraint(
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
            name="payload_shapes",
        ),
        CheckConstraint("length(preview_fingerprint) = 64", name="preview_fingerprint_length"),
        ForeignKeyConstraint(
            ["rollout_id"],
            ["training_rollouts.id"],
            name="fk_rollout_employee_impacts_rollout",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_profile_id"],
            ["employee_profiles.id"],
            name="fk_rollout_employee_impacts_employee",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_assignment_id"],
            ["training_assignments.id"],
            name="fk_rollout_employee_impacts_source_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_assignment_id"],
            ["training_assignments.id"],
            name="fk_rollout_employee_impacts_target_assignment",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_rollout_employee_impacts_rollout_employee",
            "rollout_id",
            "employee_profile_id",
        ),
    )

    rollout_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    source_assignment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    target_assignment_id: Mapped[UUID | None] = mapped_column(_uuid())
    current_required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_completed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_completed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_impact: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    warning_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    previewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
