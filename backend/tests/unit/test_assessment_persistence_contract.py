from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.db.base import Base

EXPECTED_SLICE_5_TABLES = {
    "question_generation_rules",
    "question_candidates",
    "questions",
    "question_versions",
    "question_version_translations",
    "question_options",
    "question_option_translations",
    "question_source_links",
    "assessments",
    "assessment_versions",
    "assessment_version_translations",
    "assessment_question_pools",
    "assessment_readiness",
    "assessment_attempts",
    "attempt_questions",
    "attempt_options",
    "submitted_answers",
    "attempt_device_leases",
    "attempt_results",
}

EXPECTED_SLICE_6_TABLES = EXPECTED_SLICE_5_TABLES | {"assessment_eligibilities"}


def test_slice_5_metadata_contains_the_accepted_persistence_graph() -> None:
    assert set(Base.metadata.tables) >= EXPECTED_SLICE_5_TABLES


def test_attempt_and_answer_database_invariants_are_declared() -> None:
    attempt_table = Base.metadata.tables["assessment_attempts"]
    answer_table = Base.metadata.tables["submitted_answers"]

    attempt_indexes = {item.name for item in attempt_table.indexes if isinstance(item, Index)}
    answer_constraints = {
        item.name
        for item in answer_table.constraints
        if isinstance(item, (CheckConstraint, UniqueConstraint))
    }

    assert "uq_assessment_attempts_active" in attempt_indexes
    assert "uq_submitted_answers_attempt_question" in answer_constraints
    assert "ck_submitted_answers_payload_object" in answer_constraints


def test_slice_6_metadata_supports_training_scoped_practice_and_eligibility() -> None:
    assert set(Base.metadata.tables) >= EXPECTED_SLICE_6_TABLES

    assessment_table = Base.metadata.tables["assessments"]
    version_table = Base.metadata.tables["assessment_versions"]
    eligibility_table = Base.metadata.tables["assessment_eligibilities"]

    assessment_constraints = {
        item.name for item in assessment_table.constraints if isinstance(item, CheckConstraint)
    }
    version_constraints = {
        item.name for item in version_table.constraints if isinstance(item, CheckConstraint)
    }
    eligibility_constraints = {
        item.name
        for item in eligibility_table.constraints
        if isinstance(item, (CheckConstraint, UniqueConstraint))
    }
    eligibility_indexes = {
        item.name for item in eligibility_table.indexes if isinstance(item, Index)
    }

    assert assessment_table.c.lesson_id.nullable is True
    assert "ck_assessments_scope_matches_type" in assessment_constraints
    assert version_table.c.lesson_id.nullable is True
    assert version_table.c.lesson_version_id.nullable is True
    assert version_table.c.threshold_percent.nullable is True
    assert "ck_assessment_versions_configuration_matches_scope" in version_constraints
    assert "ck_assessment_eligibilities_status_timestamps_match" in eligibility_constraints
    assert "uq_assessment_eligibilities_active" in eligibility_indexes
