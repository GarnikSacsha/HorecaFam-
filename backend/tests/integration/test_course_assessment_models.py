from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssessmentAttempt, AttemptResult
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
    make_attempt_result,
)
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.parametrize("question_count", [10, 15, 20])
async def test_course_check_preserves_full_count_without_final_exam_certification(
    db_session: AsyncSession,
    question_count: int,
) -> None:
    context = await _make_context(db_session)
    assessment = make_assessment(
        context.training,
        context.lesson_version,
        assessment_type="course_knowledge_check",
    )
    db_session.add(assessment)
    await db_session.flush()
    version = make_assessment_version(
        assessment,
        context.training_version,
        context.lesson_version,
        question_count=question_count,
        threshold_percent=None,
        feedback_policy="after_final_submission",
    )
    db_session.add(version)
    await db_session.flush()
    now = datetime.now(UTC)
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        version,
        question_count=question_count,
        status="completed",
        completed_at=now,
    )
    db_session.add(attempt)
    await db_session.flush()
    result = make_attempt_result(
        attempt,
        correct_count=question_count,
        total_count=question_count,
        score_basis_points=10000,
        pass_status=None,
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(result)
    assert result.total_count == question_count
    assert result.pass_status is None


@pytest.mark.parametrize("invalid_field", ["count", "type", "certification"])
async def test_course_check_rejects_mismatched_attempt_or_certification(
    db_session: AsyncSession,
    invalid_field: str,
) -> None:
    context = await _make_context(db_session)
    assessment = make_assessment(
        context.training,
        context.lesson_version,
        assessment_type="course_knowledge_check",
    )
    db_session.add(assessment)
    await db_session.flush()
    version = make_assessment_version(
        assessment,
        context.training_version,
        context.lesson_version,
        question_count=20,
        threshold_percent=None,
        feedback_policy="after_final_submission",
    )
    db_session.add(version)
    await db_session.flush()
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        version,
        question_count=15 if invalid_field == "count" else 20,
        assessment_type="menu_final_exam" if invalid_field == "type" else "course_knowledge_check",
        status="completed",
        completed_at=datetime.now(UTC),
    )
    record: AssessmentAttempt | AttemptResult
    if invalid_field == "certification":
        db_session.add(attempt)
        await db_session.flush()
        record = make_attempt_result(
            attempt,
            correct_count=20,
            total_count=20,
            score_basis_points=10000,
            pass_status="passed",
        )
    else:
        record = attempt
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(record)
            await db_session.flush()
