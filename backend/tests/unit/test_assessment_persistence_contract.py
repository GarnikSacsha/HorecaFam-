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
