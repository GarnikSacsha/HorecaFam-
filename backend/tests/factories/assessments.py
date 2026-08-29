from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AttemptResult,
    Question,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionOption,
    QuestionVersion,
    SubmittedAnswer,
)
from app.models.auth import Session
from app.models.identity import EmployeeProfile
from app.models.training import LessonVersion, Training, TrainingVersion
from app.models.training_assignments import TrainingAssignment


def make_question_generation_rule(**overrides: Any) -> QuestionGenerationRule:
    values: dict[str, Any] = {
        "id": uuid4(),
        "code": "menu.component.single_choice",
        "version": 1,
        "domain_type": "menu",
        "mechanic": "single_choice",
        "status": "active",
        "configuration": {},
    }
    values.update(overrides)
    return QuestionGenerationRule(**values)


def make_question_candidate(
    rule: QuestionGenerationRule,
    training_version: TrainingVersion,
    lesson_version: LessonVersion,
    **overrides: Any,
) -> QuestionCandidate:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": training_version.organization_id,
        "location_id": training_version.location_id,
        "generation_rule_id": rule.id,
        "training_version_id": training_version.id,
        "lesson_version_id": lesson_version.id,
        "mechanic": "single_choice",
        "prompt_payload": {"text": "Choose a verified component"},
        "answer_payload": {"correct_keys": ["correct"]},
        "explanation_payload": {"text": "Verified Menu fact"},
        "is_critical": False,
        "source_fingerprint": "a" * 64,
        "status": "needs_review",
        "revision": 0,
    }
    values.update(overrides)
    return QuestionCandidate(**values)


def make_question(candidate: QuestionCandidate, **overrides: Any) -> Question:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": candidate.organization_id,
        "location_id": candidate.location_id,
    }
    values.update(overrides)
    return Question(**values)


def make_question_version(
    question: Question,
    candidate: QuestionCandidate,
    user_id: Any,
    **overrides: Any,
) -> QuestionVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": candidate.organization_id,
        "location_id": candidate.location_id,
        "question_id": question.id,
        "candidate_id": candidate.id,
        "version_number": 1,
        "status": "published",
        "mechanic": candidate.mechanic,
        "prompt_payload": candidate.prompt_payload,
        "grading_payload": candidate.answer_payload,
        "explanation_payload": candidate.explanation_payload,
        "is_critical": candidate.is_critical,
        "source_fingerprint": candidate.source_fingerprint,
        "published_by_user_id": user_id,
        "published_at": datetime.now(UTC),
    }
    values.update(overrides)
    return QuestionVersion(**values)


def make_question_option(
    question_version: QuestionVersion,
    position: int,
    **overrides: Any,
) -> QuestionOption:
    values: dict[str, Any] = {
        "id": uuid4(),
        "question_version_id": question_version.id,
        "stable_key": f"option-{position}",
        "position": position,
        "payload": {"text": f"Option {position}"},
        "is_correct": position == 0,
    }
    values.update(overrides)
    return QuestionOption(**values)


def make_assessment(
    training: Training,
    lesson_version: LessonVersion,
    **overrides: Any,
) -> Assessment:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": training.organization_id,
        "location_id": training.location_id,
        "training_id": training.id,
        "lesson_id": lesson_version.lesson_id,
        "assessment_type": "interactive_training",
    }
    values.update(overrides)
    return Assessment(**values)


def make_assessment_version(
    assessment: Assessment,
    training_version: TrainingVersion,
    lesson_version: LessonVersion,
    **overrides: Any,
) -> AssessmentVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": assessment.organization_id,
        "location_id": assessment.location_id,
        "assessment_id": assessment.id,
        "training_version_id": training_version.id,
        "lesson_id": lesson_version.lesson_id,
        "lesson_version_id": lesson_version.id,
        "version_number": 1,
        "status": "published",
        "question_count": 5,
        "feedback_policy": "immediate",
        "sampling_configuration": {},
    }
    values.update(overrides)
    return AssessmentVersion(**values)


def make_assessment_question_pool(
    assessment_version: AssessmentVersion,
    question_version: QuestionVersion,
    **overrides: Any,
) -> AssessmentQuestionPool:
    values: dict[str, Any] = {
        "id": uuid4(),
        "assessment_version_id": assessment_version.id,
        "question_version_id": question_version.id,
        "coverage_key": "menu-item-1",
        "mechanic": question_version.mechanic,
        "weight": 1,
        "eligible": True,
    }
    values.update(overrides)
    return AssessmentQuestionPool(**values)


def make_assessment_readiness(
    assessment_version: AssessmentVersion,
    **overrides: Any,
) -> AssessmentReadiness:
    values: dict[str, Any] = {
        "id": uuid4(),
        "assessment_version_id": assessment_version.id,
        "status": "warning",
        "eligible_count": 5,
        "required_count": 5,
        "coverage_evidence": {},
        "rotation_supported": False,
        "basis_fingerprint": "b" * 64,
        "blocking_codes": [],
        "warning_codes": ["ROTATION_LIMITED"],
        "computed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return AssessmentReadiness(**values)


def make_assessment_attempt(
    employee: EmployeeProfile,
    assignment: TrainingAssignment,
    assessment_version: AssessmentVersion,
    **overrides: Any,
) -> AssessmentAttempt:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": assignment.organization_id,
        "location_id": assignment.location_id,
        "training_id": assignment.training_id,
        "employee_profile_id": employee.id,
        "assignment_id": assignment.id,
        "assessment_version_id": assessment_version.id,
        "status": "in_progress",
        "presentation_locale": "uk",
        "question_count": 5,
        "snapshot_schema_version": 1,
        "started_at": now,
        "last_activity_at": now,
        "expires_at": now + timedelta(days=7),
    }
    values.update(overrides)
    return AssessmentAttempt(**values)


def make_attempt_question(
    attempt: AssessmentAttempt,
    question_version: QuestionVersion,
    **overrides: Any,
) -> AttemptQuestion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "attempt_id": attempt.id,
        "question_version_id": question_version.id,
        "position": 0,
        "mechanic": question_version.mechanic,
        "prompt_payload": question_version.prompt_payload,
        "grading_payload": question_version.grading_payload,
        "explanation_payload": question_version.explanation_payload,
        "is_critical": question_version.is_critical,
        "coverage_key": "menu-item-1",
        "presentation_locale": attempt.presentation_locale,
        "provenance_snapshot": {"fingerprint": question_version.source_fingerprint},
        "version_snapshot": {"question_version_id": str(question_version.id)},
    }
    values.update(overrides)
    return AttemptQuestion(**values)


def make_attempt_option(
    attempt_question: AttemptQuestion,
    source_option: QuestionOption,
    **overrides: Any,
) -> AttemptOption:
    values: dict[str, Any] = {
        "id": uuid4(),
        "attempt_question_id": attempt_question.id,
        "source_option_id": source_option.id,
        "position": source_option.position,
        "payload": source_option.payload,
        "is_correct": source_option.is_correct,
    }
    values.update(overrides)
    return AttemptOption(**values)


def make_submitted_answer(
    attempt: AssessmentAttempt,
    attempt_question: AttemptQuestion,
    **overrides: Any,
) -> SubmittedAnswer:
    values: dict[str, Any] = {
        "id": uuid4(),
        "attempt_id": attempt.id,
        "attempt_question_id": attempt_question.id,
        "answer_payload": {"option_ids": []},
        "is_correct": True,
        "is_critical_error": False,
        "idempotency_key": str(uuid4()),
    }
    values.update(overrides)
    return SubmittedAnswer(**values)


def make_attempt_device_lease(
    attempt: AssessmentAttempt,
    auth_session: Session,
    **overrides: Any,
) -> AttemptDeviceLease:
    values: dict[str, Any] = {
        "id": uuid4(),
        "attempt_id": attempt.id,
        "session_id": auth_session.id,
        "generation": 1,
    }
    values.update(overrides)
    return AttemptDeviceLease(**values)


def make_attempt_result(attempt: AssessmentAttempt, **overrides: Any) -> AttemptResult:
    values: dict[str, Any] = {
        "id": uuid4(),
        "attempt_id": attempt.id,
        "correct_count": 1,
        "total_count": 5,
        "score_basis_points": 2000,
        "knowledge_level": "very_weak",
        "pass_status": None,
        "critical_error_count": 0,
        "section_breakdown": {},
        "completed_at": attempt.completed_at or datetime.now(UTC),
    }
    values.update(overrides)
    return AttemptResult(**values)
