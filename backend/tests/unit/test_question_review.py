from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AssessmentReadiness, AssessmentVersion, QuestionCandidate, TrainingVersion
from app.schemas.assessment import (
    CandidateAnswerPayload,
    CandidateEditedPayload,
    CandidateExplanationPayload,
    CandidateOption,
    CandidatePromptPayload,
)
from app.services.question_review import (
    _validated_payloads,
    derive_readiness_state,
    get_interactive_training_readiness,
    reject_question_candidate,
)


def _candidate(*, status: str = "needs_review", revision: int = 0) -> QuestionCandidate:
    return QuestionCandidate(
        id=uuid4(),
        organization_id=uuid4(),
        location_id=uuid4(),
        generation_rule_id=uuid4(),
        training_version_id=uuid4(),
        lesson_version_id=uuid4(),
        mechanic="single_choice",
        prompt_payload={
            "locale": "uk",
            "stem": "Оберіть правильну страву",
            "options": [
                {"stable_key": "borshch", "text": "Борщ"},
                {"stable_key": "salad", "text": "Салат"},
            ],
        },
        answer_payload={"correct_option_keys": ["borshch"]},
        explanation_payload={"locale": "uk", "text": "Факт із меню"},
        is_critical=False,
        source_fingerprint="a" * 64,
        status=status,
        revision=revision,
        reviewed_at=None,
        rejection_reason_code=None,
    )


def test_readiness_state_distinguishes_blocked_warning_and_ready() -> None:
    assert derive_readiness_state(4) == (
        "blocked",
        False,
        ["INSUFFICIENT_QUESTION_POOL"],
        [],
    )
    assert derive_readiness_state(5) == (
        "warning",
        False,
        [],
        ["REPEAT_ROTATION_LIMITED"],
    )
    assert derive_readiness_state(10) == ("ready", True, [], [])


def test_candidate_edit_can_change_copy_but_not_provenance_bound_answer() -> None:
    candidate = _candidate()
    edited = CandidateEditedPayload(
        prompt_payload=CandidatePromptPayload(
            stem="Оберіть страву з перевіреного меню",
            options=[
                CandidateOption(stable_key="borshch", text="Борщ"),
                CandidateOption(stable_key="salad", text="Салат"),
            ],
        ),
        answer_payload=CandidateAnswerPayload(correct_option_keys=["borshch"]),
        explanation_payload=CandidateExplanationPayload(text="Підтверджено меню"),
    )

    prompt, answer, explanation = _validated_payloads(candidate, edited)
    assert prompt.stem == "Оберіть страву з перевіреного меню"
    assert answer.correct_option_keys == ["borshch"]
    assert explanation.text == "Підтверджено меню"

    changed_answer = edited.model_copy(
        update={
            "answer_payload": CandidateAnswerPayload(correct_option_keys=["salad"]),
        }
    )
    with pytest.raises(APIError) as raised:
        _validated_payloads(candidate, changed_answer)
    assert raised.value.code == "QUESTION_PROVENANCE_INVALID"


@pytest.mark.asyncio
async def test_reject_candidate_records_reason_and_audit() -> None:
    candidate = _candidate()
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=candidate),
        scalars=AsyncMock(return_value=[]),
        add=Mock(),
        commit=AsyncMock(),
    )
    now = datetime.now(UTC)
    actor_id = uuid4()

    response = await reject_question_candidate(
        cast(AsyncSession, db),
        organization_id=candidate.organization_id,
        location_id=candidate.location_id,
        candidate_id=candidate.id,
        expected_revision=0,
        reason_code="AMBIGUOUS_WORDING",
        actor_user_id=actor_id,
        request_id=uuid4(),
        now=now,
    )

    assert response.status == "rejected"
    assert response.revision == 1
    assert response.rejection_reason_code == "AMBIGUOUS_WORDING"
    assert candidate.reviewed_by_user_id == actor_id
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "revision", "expected_revision", "error_code"),
    [
        ("needs_review", 1, 0, "REVISION_CONFLICT"),
        ("stale", 0, 0, "QUESTION_CANDIDATE_STALE"),
        ("approved", 0, 0, "REVISION_CONFLICT"),
    ],
)
async def test_reject_candidate_enforces_review_state(
    status: str,
    revision: int,
    expected_revision: int,
    error_code: str,
) -> None:
    candidate = _candidate(status=status, revision=revision)
    db = SimpleNamespace(scalar=AsyncMock(return_value=candidate))

    with pytest.raises(APIError) as raised:
        await reject_question_candidate(
            cast(AsyncSession, db),
            organization_id=candidate.organization_id,
            location_id=candidate.location_id,
            candidate_id=candidate.id,
            expected_revision=expected_revision,
            reason_code="AMBIGUOUS_WORDING",
            actor_user_id=uuid4(),
            request_id=uuid4(),
            now=datetime.now(UTC),
        )
    assert raised.value.code == error_code


@pytest.mark.asyncio
async def test_training_readiness_returns_published_lesson_state() -> None:
    organization_id = uuid4()
    location_id = uuid4()
    training_version = TrainingVersion(
        id=uuid4(),
        organization_id=organization_id,
        location_id=location_id,
        training_id=uuid4(),
        version_number=1,
        status="published",
    )
    assessment_version = AssessmentVersion(
        id=uuid4(),
        organization_id=organization_id,
        location_id=location_id,
        assessment_id=uuid4(),
        training_version_id=training_version.id,
        lesson_id=uuid4(),
        lesson_version_id=uuid4(),
        version_number=1,
        status="published",
        question_count=5,
        feedback_policy="immediate",
        sampling_configuration={},
    )
    now = datetime.now(UTC)
    readiness = AssessmentReadiness(
        assessment_version_id=assessment_version.id,
        status="warning",
        eligible_count=5,
        required_count=5,
        coverage_evidence={"distinct_source_count": 5},
        rotation_supported=False,
        basis_fingerprint="b" * 64,
        blocking_codes=[],
        warning_codes=["REPEAT_ROTATION_LIMITED"],
        computed_at=now,
    )
    result = SimpleNamespace(all=lambda: [(assessment_version, readiness)])
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=training_version),
        execute=AsyncMock(return_value=result),
    )

    response = await get_interactive_training_readiness(
        cast(AsyncSession, db),
        organization_id=organization_id,
        location_id=location_id,
        training_version_id=training_version.id,
    )

    assert response.training_version_id == training_version.id
    assert len(response.lessons) == 1
    assert response.lessons[0].status == "warning"
    assert response.lessons[0].can_start is True


@pytest.mark.asyncio
async def test_training_readiness_hides_foreign_or_missing_version() -> None:
    db = SimpleNamespace(scalar=AsyncMock(return_value=None))

    with pytest.raises(APIError) as raised:
        await get_interactive_training_readiness(
            cast(AsyncSession, db),
            organization_id=uuid4(),
            location_id=uuid4(),
            training_version_id=uuid4(),
        )
    assert raised.value.code == "RESOURCE_NOT_FOUND"
