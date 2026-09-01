from datetime import datetime
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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    AssessmentAttemptStatus,
    AssessmentReadinessStatus,
    AssessmentType,
    AssessmentVersionStatus,
    GenerationRuleStatus,
    QuestionCandidateStatus,
    QuestionVersionStatus,
)


def _uuid() -> PostgreSQLUUID[UUID]:
    return PostgreSQLUUID(as_uuid=True)


MECHANICS = "'single_choice', 'multiple_choice', 'matching', 'ordering', 'assembly', 'recognition'"


class QuestionGenerationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_generation_rules"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_question_generation_rules_code_version"),
        CheckConstraint("length(btrim(code)) BETWEEN 1 AND 100", name="code_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("domain_type = 'menu'", name="domain_type_menu"),
        CheckConstraint(f"mechanic IN ({MECHANICS})", name="mechanic_allowed"),
        CheckConstraint("status IN ('active', 'retired')", name="status_allowed"),
        CheckConstraint("jsonb_typeof(configuration) = 'object'", name="configuration_object"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="menu")
    mechanic: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=GenerationRuleStatus.ACTIVE.value,
        server_default="active",
    )
    configuration: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class QuestionCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_candidates"
    __table_args__ = (
        UniqueConstraint(
            "generation_rule_id",
            "lesson_version_id",
            "source_fingerprint",
            name="uq_question_candidates_generation_fingerprint",
        ),
        UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_question_candidates_scope"
        ),
        CheckConstraint(f"mechanic IN ({MECHANICS})", name="mechanic_allowed"),
        CheckConstraint(
            "status IN ('needs_review', 'approved', 'rejected', 'stale')",
            name="status_allowed",
        ),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint("length(source_fingerprint) = 64", name="source_fingerprint_length"),
        CheckConstraint("jsonb_typeof(prompt_payload) = 'object'", name="prompt_payload_object"),
        CheckConstraint("jsonb_typeof(answer_payload) = 'object'", name="answer_payload_object"),
        CheckConstraint(
            "jsonb_typeof(explanation_payload) = 'object'", name="explanation_payload_object"
        ),
        CheckConstraint(
            "(status = 'needs_review' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR "
            "(status IN ('approved', 'rejected', 'stale'))",
            name="review_state_match",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_question_candidates_location_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_question_candidates_training_version_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_question_candidates_review_queue",
            "organization_id",
            "location_id",
            "status",
            "created_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    generation_rule_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_generation_rules.id", ondelete="RESTRICT"), nullable=False
    )
    training_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    lesson_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("lesson_versions.id", ondelete="RESTRICT"), nullable=False
    )
    mechanic: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    answer_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explanation_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=QuestionCandidateStatus.NEEDS_REVIEW.value,
        server_default="needs_review",
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason_code: Mapped[str | None] = mapped_column(String(64))


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "location_id", name="uq_questions_scope"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_questions_location_scope",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)


class QuestionVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_versions"
    __table_args__ = (
        UniqueConstraint("question_id", "version_number", name="uq_question_versions_number"),
        UniqueConstraint("id", "question_id", name="uq_question_versions_question_scope"),
        UniqueConstraint("id", "organization_id", "location_id", name="uq_question_versions_scope"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint(f"mechanic IN ({MECHANICS})", name="mechanic_allowed"),
        CheckConstraint("status IN ('published', 'stale', 'archived')", name="status_allowed"),
        CheckConstraint("length(source_fingerprint) = 64", name="source_fingerprint_length"),
        CheckConstraint("jsonb_typeof(prompt_payload) = 'object'", name="prompt_payload_object"),
        CheckConstraint("jsonb_typeof(grading_payload) = 'object'", name="grading_payload_object"),
        CheckConstraint(
            "jsonb_typeof(explanation_payload) = 'object'", name="explanation_payload_object"
        ),
        ForeignKeyConstraint(
            ["question_id", "organization_id", "location_id"],
            ["questions.id", "questions.organization_id", "questions.location_id"],
            name="fk_question_versions_question_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["candidate_id", "organization_id", "location_id"],
            [
                "question_candidates.id",
                "question_candidates.organization_id",
                "question_candidates.location_id",
            ],
            name="fk_question_versions_candidate_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_question_versions_scope_status", "organization_id", "location_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    question_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=QuestionVersionStatus.PUBLISHED.value,
        server_default="published",
    )
    mechanic: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    grading_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explanation_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    published_by_user_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuestionVersionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_version_translations"
    __table_args__ = (
        UniqueConstraint(
            "question_version_id", "locale", name="uq_question_version_translations_locale"
        ),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("jsonb_typeof(prompt_payload) = 'object'", name="prompt_payload_object"),
        CheckConstraint(
            "jsonb_typeof(explanation_payload) = 'object'", name="explanation_payload_object"
        ),
    )

    question_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    prompt_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explanation_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class QuestionOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint(
            "question_version_id", "stable_key", name="uq_question_options_stable_key"
        ),
        UniqueConstraint("question_version_id", "position", name="uq_question_options_position"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("length(btrim(stable_key)) BETWEEN 1 AND 100", name="stable_key_length"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
    )

    question_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False
    )
    stable_key: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class QuestionOptionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_option_translations"
    __table_args__ = (
        UniqueConstraint(
            "question_option_id", "locale", name="uq_question_option_translations_locale"
        ),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
    )

    question_option_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_options.id", ondelete="RESTRICT"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class QuestionSourceLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_source_links"
    __table_args__ = (
        CheckConstraint(
            "source_role IN ('correct_fact', 'distractor_basis', "
            "'explanation_source', 'critical_fact')",
            name="source_role_allowed",
        ),
        CheckConstraint(
            "num_nonnulls(question_candidate_id, question_version_id) = 1",
            name="exactly_one_owner",
        ),
        CheckConstraint(
            "num_nonnulls(menu_item_version_id, menu_item_version_component_id, "
            "menu_item_version_allergen_id) = 1",
            name="exactly_one_source",
        ),
        ForeignKeyConstraint(
            ["question_version_id", "organization_id", "location_id"],
            [
                "question_versions.id",
                "question_versions.organization_id",
                "question_versions.location_id",
            ],
            name="fk_question_source_links_question_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["question_candidate_id", "organization_id", "location_id"],
            [
                "question_candidates.id",
                "question_candidates.organization_id",
                "question_candidates.location_id",
            ],
            name="fk_question_source_links_candidate_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_question_source_links_candidate_role", "question_candidate_id", "source_role"),
        Index("ix_question_source_links_question_role", "question_version_id", "source_role"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    question_candidate_id: Mapped[UUID | None] = mapped_column(_uuid())
    question_version_id: Mapped[UUID | None] = mapped_column(_uuid())
    source_role: Mapped[str] = mapped_column(String(32), nullable=False)
    menu_item_version_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("menu_item_versions.id", ondelete="RESTRICT")
    )
    menu_item_version_component_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("menu_item_version_components.id", ondelete="RESTRICT")
    )
    menu_item_version_allergen_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("menu_item_version_allergens.id", ondelete="RESTRICT")
    )


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("lesson_id", "assessment_type", name="uq_assessments_lesson_type"),
        UniqueConstraint("id", "organization_id", "location_id", name="uq_assessments_scope"),
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_assessments_training_scope",
        ),
        CheckConstraint(
            "assessment_type IN ('interactive_training', "
            "'whole_menu_knowledge_check', 'menu_final_exam')",
            name="assessment_type_allowed",
        ),
        CheckConstraint(
            "(assessment_type = 'interactive_training' AND lesson_id IS NOT NULL) OR "
            "(assessment_type IN ('whole_menu_knowledge_check', 'menu_final_exam') "
            "AND lesson_id IS NULL)",
            name="scope_matches_type",
        ),
        ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_assessments_training_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_assessments_training_type",
            "training_id",
            "assessment_type",
            unique=True,
            postgresql_where=text("lesson_id IS NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    lesson_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("lessons.id", ondelete="RESTRICT")
    )
    assessment_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AssessmentType.INTERACTIVE_TRAINING.value
    )


class AssessmentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_versions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "version_number", name="uq_assessment_versions_number"),
        UniqueConstraint("id", "assessment_id", name="uq_assessment_versions_assessment_scope"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status_allowed"),
        CheckConstraint(
            "(lesson_id IS NOT NULL AND lesson_version_id IS NOT NULL "
            "AND question_count = 5 AND threshold_percent IS NULL "
            "AND feedback_policy = 'immediate') OR "
            "(lesson_id IS NULL AND lesson_version_id IS NULL "
            "AND ((question_count = 10 AND threshold_percent = 40) "
            "OR (question_count = 20 AND threshold_percent = 70)) "
            "AND feedback_policy = 'after_final_submission')",
            name="configuration_matches_scope",
        ),
        CheckConstraint(
            "jsonb_typeof(sampling_configuration) = 'object'", name="sampling_configuration_object"
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "location_id"],
            ["assessments.id", "assessments.organization_id", "assessments.location_id"],
            name="fk_assessment_versions_assessment_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_assessment_versions_training_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            name="fk_assessment_versions_lesson_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_assessment_versions_training_lesson_status",
            "training_version_id",
            "lesson_version_id",
            "status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    lesson_id: Mapped[UUID | None] = mapped_column(_uuid())
    lesson_version_id: Mapped[UUID | None] = mapped_column(_uuid())
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AssessmentVersionStatus.DRAFT.value,
        server_default="draft",
    )
    question_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    threshold_percent: Mapped[int | None] = mapped_column(Integer)
    feedback_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="immediate", server_default="immediate"
    )
    sampling_configuration: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentVersionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_version_translations"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id", "locale", name="uq_assessment_version_translations_locale"
        ),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="title_length"),
    )

    assessment_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_versions.id", ondelete="RESTRICT"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class AssessmentQuestionPool(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_question_pools"
    __table_args__ = (
        UniqueConstraint(
            "assessment_version_id",
            "question_version_id",
            name="uq_assessment_question_pools_question",
        ),
        CheckConstraint("weight BETWEEN 1 AND 100", name="weight_range"),
        CheckConstraint(
            "(eligible = true AND exclusion_reason IS NULL) OR "
            "(eligible = false AND exclusion_reason IS NOT NULL)",
            name="eligibility_reason_match",
        ),
        Index("ix_assessment_question_pools_eligible", "assessment_version_id", "eligible"),
    )

    assessment_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_versions.id", ondelete="RESTRICT"), nullable=False
    )
    question_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False
    )
    coverage_key: Mapped[str] = mapped_column(String(200), nullable=False)
    mechanic: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    exclusion_reason: Mapped[str | None] = mapped_column(String(64))


class AssessmentReadiness(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_readiness"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", name="uq_assessment_readiness_version"),
        CheckConstraint(
            "status IN ('processing', 'ready', 'warning', 'blocked')", name="status_allowed"
        ),
        CheckConstraint(
            "eligible_count >= 0 AND required_count IN (5, 10, 20)", name="counts_valid"
        ),
        CheckConstraint("length(basis_fingerprint) = 64", name="basis_fingerprint_length"),
        CheckConstraint(
            "jsonb_typeof(coverage_evidence) = 'object'", name="coverage_evidence_object"
        ),
        CheckConstraint("jsonb_typeof(blocking_codes) = 'array'", name="blocking_codes_array"),
        CheckConstraint("jsonb_typeof(warning_codes) = 'array'", name="warning_codes_array"),
    )

    assessment_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_versions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AssessmentReadinessStatus.PROCESSING.value,
        server_default="processing",
    )
    eligible_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    required_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    coverage_evidence: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    rotation_supported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    basis_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    blocking_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    warning_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_assessment_attempts_scope",
        ),
        UniqueConstraint(
            "id",
            "employee_profile_id",
            "assignment_id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_assessment_attempts_eligibility_scope",
        ),
        UniqueConstraint(
            "id",
            "employee_profile_id",
            "organization_id",
            "location_id",
            "training_id",
            name="uq_assessment_attempts_employee_training_scope",
        ),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'expired', 'invalidated')",
            name="status_allowed",
        ),
        CheckConstraint("presentation_locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("question_count IN (5, 10, 20)", name="question_count_allowed"),
        CheckConstraint("snapshot_schema_version >= 1", name="snapshot_schema_version_positive"),
        CheckConstraint("expires_at > started_at", name="expiry_after_start"),
        CheckConstraint(
            "(status = 'in_progress' AND completed_at IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status IN ('expired', 'invalidated'))",
            name="completion_state_match",
        ),
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_assessment_attempts_employee_scope",
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
            name="fk_assessment_attempts_assignment_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_assessment_attempts_active",
            "employee_profile_id",
            "assignment_id",
            "assessment_version_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
        Index(
            "ix_assessment_attempts_employee_completed",
            "employee_profile_id",
            "assessment_version_id",
            "completed_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assessment_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_versions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AssessmentAttemptStatus.IN_PROGRESS.value,
        server_default="in_progress",
    )
    presentation_locale: Mapped[str] = mapped_column(String(8), nullable=False)
    question_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    snapshot_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidation_code: Mapped[str | None] = mapped_column(String(64))


class AttemptQuestion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attempt_questions"
    __table_args__ = (
        UniqueConstraint("attempt_id", "position", name="uq_attempt_questions_position"),
        UniqueConstraint("attempt_id", "question_version_id", name="uq_attempt_questions_version"),
        UniqueConstraint("id", "attempt_id", name="uq_attempt_questions_attempt_scope"),
        CheckConstraint("position BETWEEN 0 AND 19", name="position_range"),
        CheckConstraint(f"mechanic IN ({MECHANICS})", name="mechanic_allowed"),
        CheckConstraint("jsonb_typeof(prompt_payload) = 'object'", name="prompt_payload_object"),
        CheckConstraint("jsonb_typeof(grading_payload) = 'object'", name="grading_payload_object"),
        CheckConstraint(
            "jsonb_typeof(explanation_payload) = 'object'", name="explanation_payload_object"
        ),
        CheckConstraint(
            "jsonb_typeof(provenance_snapshot) = 'object'", name="provenance_snapshot_object"
        ),
        CheckConstraint(
            "jsonb_typeof(version_snapshot) = 'object'", name="version_snapshot_object"
        ),
        Index("ix_attempt_questions_attempt_position", "attempt_id", "position"),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    question_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    mechanic: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    grading_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explanation_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    coverage_key: Mapped[str] = mapped_column(String(200), nullable=False)
    presentation_locale: Mapped[str] = mapped_column(String(8), nullable=False)
    provenance_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    version_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AttemptOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attempt_options"
    __table_args__ = (
        UniqueConstraint("attempt_question_id", "position", name="uq_attempt_options_position"),
        UniqueConstraint(
            "attempt_question_id", "source_option_id", name="uq_attempt_options_source"
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
    )

    attempt_question_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("attempt_questions.id", ondelete="RESTRICT"), nullable=False
    )
    source_option_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("question_options.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SubmittedAnswer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "submitted_answers"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "attempt_question_id", name="uq_submitted_answers_attempt_question"
        ),
        UniqueConstraint("attempt_id", "idempotency_key", name="uq_submitted_answers_idempotency"),
        UniqueConstraint(
            "id",
            "attempt_id",
            "attempt_question_id",
            name="uq_submitted_answers_source_scope",
        ),
        CheckConstraint("jsonb_typeof(answer_payload) = 'object'", name="payload_object"),
        ForeignKeyConstraint(
            ["attempt_question_id", "attempt_id"],
            ["attempt_questions.id", "attempt_questions.attempt_id"],
            name="fk_submitted_answers_question_scope",
            ondelete="RESTRICT",
        ),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_question_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    answer_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_critical_error: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AttemptDeviceLease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attempt_device_leases"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_attempt_device_leases_attempt"),
        CheckConstraint("generation >= 1", name="generation_positive"),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AttemptResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attempt_results"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_attempt_results_attempt"),
        UniqueConstraint("id", "attempt_id", name="uq_attempt_results_source_scope"),
        CheckConstraint("correct_count BETWEEN 0 AND total_count", name="correct_count_range"),
        CheckConstraint("total_count IN (5, 10, 20)", name="total_count_allowed"),
        CheckConstraint("score_basis_points BETWEEN 0 AND 10000", name="score_range"),
        CheckConstraint(
            "knowledge_level IN ('very_weak', 'weak', 'good', 'strong')",
            name="knowledge_level_allowed",
        ),
        CheckConstraint(
            "(total_count IN (5, 10) AND pass_status IS NULL) OR "
            "(total_count = 20 AND pass_status IN ('passed', 'failed'))",
            name="pass_status_matches_count",
        ),
        CheckConstraint(
            "critical_error_count BETWEEN 0 AND total_count", name="critical_error_count_range"
        ),
        CheckConstraint(
            "jsonb_typeof(section_breakdown) = 'object'", name="section_breakdown_object"
        ),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    score_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    knowledge_level: Mapped[str] = mapped_column(String(16), nullable=False)
    pass_status: Mapped[str | None] = mapped_column(String(16))
    critical_error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    section_breakdown: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssessmentEligibility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_eligibilities"
    __table_args__ = (
        UniqueConstraint("earned_by_attempt_id", name="uq_assessment_eligibilities_earned_attempt"),
        CheckConstraint("status IN ('earned', 'reset')", name="status_allowed"),
        CheckConstraint(
            "(status = 'earned' AND reset_at IS NULL AND reset_by_user_id IS NULL "
            "AND reset_reason IS NULL) OR "
            "(status = 'reset' AND reset_at IS NOT NULL AND reset_by_user_id IS NOT NULL "
            "AND length(btrim(reset_reason)) BETWEEN 1 AND 500)",
            name="status_timestamps_match",
        ),
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_assessment_eligibilities_employee_scope",
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
            name="fk_assessment_eligibilities_assignment_scope",
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
            name="fk_assessment_eligibilities_target_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        Index(
            "uq_assessment_eligibilities_active",
            "employee_profile_id",
            "assignment_id",
            "target_assessment_id",
            unique=True,
            postgresql_where=text("status = 'earned'"),
        ),
        Index(
            "ix_assessment_eligibilities_employee_history",
            "employee_profile_id",
            "target_assessment_id",
            "earned_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    employee_profile_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    target_assessment_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    earned_by_attempt_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="earned", server_default="earned"
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reset_reason: Mapped[str | None] = mapped_column(String(500))
