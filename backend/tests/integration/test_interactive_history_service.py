from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AssessmentAttempt,
    AssessmentQuestionPool,
    LessonCompletion,
    OrganizationMembership,
    QuestionVersion,
    TrainingAssignment,
)
from app.schemas.assessment import SingleChoiceSubmission
from app.services.interactive_answers import submit_interactive_answer
from app.services.interactive_attempts import start_or_resume_interactive_attempt
from app.services.interactive_history import get_lesson_interactive_training_summary
from tests.factories.assessments import (
    make_assessment_attempt,
    make_assessment_question_pool,
    make_assessment_readiness,
    make_assessment_version,
    make_attempt_result,
)
from tests.factories.interactive_training import (
    InteractiveRuntimeContext,
    arrange_interactive_runtime,
)


async def _add_completed_attempt(
    db: AsyncSession,
    *,
    context: InteractiveRuntimeContext,
    completed_at: datetime,
    correct_count: int,
) -> AssessmentAttempt:
    attempt = make_assessment_attempt(
        context.persistence.employee,
        context.persistence.assignment,
        context.persistence.assessment_version,
        status="completed",
        completed_at=completed_at,
        started_at=completed_at - timedelta(minutes=2),
        last_activity_at=completed_at,
        expires_at=completed_at + timedelta(days=7),
    )
    db.add(attempt)
    await db.flush()
    db.add(
        make_attempt_result(
            attempt,
            correct_count=correct_count,
            score_basis_points=correct_count * 2000,
            knowledge_level="strong" if correct_count >= 4 else "weak",
            completed_at=completed_at,
        )
    )
    await db.flush()
    return attempt


@pytest.mark.integration
async def test_summary_separates_latest_and_best_without_mutating_training_state(
    db_session: AsyncSession,
) -> None:
    context = await arrange_interactive_runtime(db_session, token_prefix="1")
    now = datetime.now(UTC)
    older_best_attempt = await _add_completed_attempt(
        db_session,
        context=context,
        completed_at=now - timedelta(days=2),
        correct_count=5,
    )
    best_attempt = await _add_completed_attempt(
        db_session,
        context=context,
        completed_at=now - timedelta(days=1, hours=12),
        correct_count=5,
    )
    latest_attempt = await _add_completed_attempt(
        db_session,
        context=context,
        completed_at=now - timedelta(days=1),
        correct_count=2,
    )
    counts_before = (
        await db_session.scalar(select(func.count()).select_from(TrainingAssignment)),
        await db_session.scalar(select(func.count()).select_from(LessonCompletion)),
        await db_session.scalar(select(func.count()).select_from(AssessmentAttempt)),
    )

    summary = await get_lesson_interactive_training_summary(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        lesson_id=context.persistence.lesson_version.lesson_id,
        session_id=context.session.id,
    )

    assert summary.availability == "ready"
    assert summary.can_start is True
    assert summary.reason_codes == ["ROTATION_LIMITED"]
    assert summary.active_attempt is not None
    assert summary.active_attempt.id == context.attempt.id
    assert summary.active_attempt.presentation_locale == "uk"
    assert summary.latest is not None and summary.latest.attempt_id == latest_attempt.id
    assert summary.best is not None and summary.best.attempt_id == best_attempt.id
    assert [item.attempt_id for item in summary.history] == [
        latest_attempt.id,
        best_attempt.id,
        older_best_attempt.id,
    ]
    assert all(item.is_current for item in summary.history)
    assert counts_before == (
        await db_session.scalar(select(func.count()).select_from(TrainingAssignment)),
        await db_session.scalar(select(func.count()).select_from(LessonCompletion)),
        await db_session.scalar(select(func.count()).select_from(AssessmentAttempt)),
    )


@pytest.mark.integration
async def test_best_uses_full_current_history_while_returned_history_is_bounded(
    db_session: AsyncSession,
) -> None:
    context = await arrange_interactive_runtime(db_session, token_prefix="6")
    now = datetime.now(UTC)
    oldest_best = await _add_completed_attempt(
        db_session,
        context=context,
        completed_at=now - timedelta(days=30),
        correct_count=5,
    )
    latest = None
    for index in range(20):
        latest = await _add_completed_attempt(
            db_session,
            context=context,
            completed_at=now - timedelta(days=20 - index),
            correct_count=1,
        )

    summary = await get_lesson_interactive_training_summary(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        lesson_id=context.persistence.lesson_version.lesson_id,
        session_id=context.session.id,
    )

    assert latest is not None
    assert len(summary.history) == 20
    assert all(item.attempt_id != oldest_best.id for item in summary.history)
    assert summary.latest is not None and summary.latest.attempt_id == latest.id
    assert summary.best is not None and summary.best.attempt_id == oldest_best.id


@pytest.mark.integration
async def test_new_assessment_scope_retains_old_history_but_resets_current_latest_and_best(
    db_session: AsyncSession,
) -> None:
    context = await arrange_interactive_runtime(db_session, token_prefix="2")
    old_attempt = await _add_completed_attempt(
        db_session,
        context=context,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        correct_count=5,
    )
    new_version = make_assessment_version(
        context.persistence.assessment,
        context.persistence.training_version,
        context.persistence.lesson_version,
        version_number=2,
    )
    db_session.add(new_version)
    await db_session.flush()
    old_pool = list(
        await db_session.scalars(
            select(AssessmentQuestionPool).where(
                AssessmentQuestionPool.assessment_version_id
                == context.persistence.assessment_version.id
            )
        )
    )
    for pool in old_pool:
        question_version = await db_session.get(QuestionVersion, pool.question_version_id)
        assert question_version is not None
        db_session.add(
            make_assessment_question_pool(
                new_version,
                question_version,
                coverage_key=pool.coverage_key,
            )
        )
    db_session.add(make_assessment_readiness(new_version, status="ready"))
    await db_session.flush()

    summary = await get_lesson_interactive_training_summary(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        lesson_id=context.persistence.lesson_version.lesson_id,
        session_id=context.session.id,
    )

    assert summary.assessment_version_id == new_version.id
    assert summary.latest is None
    assert summary.best is None
    assert any(
        item.attempt_id == old_attempt.id and not item.is_current for item in summary.history
    )
    assert summary.active_attempt is None


@pytest.mark.integration
async def test_paused_employee_can_read_history_but_cannot_start_and_foreign_lesson_is_hidden(
    db_session: AsyncSession,
) -> None:
    context = await arrange_interactive_runtime(db_session, token_prefix="3")
    await _add_completed_attempt(
        db_session,
        context=context,
        completed_at=datetime.now(UTC) - timedelta(hours=1),
        correct_count=4,
    )
    membership = await db_session.get(
        OrganizationMembership, context.persistence.employee.membership_id
    )
    assert membership is not None
    membership.training_participation_status = "paused"
    await db_session.flush()

    summary = await get_lesson_interactive_training_summary(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        lesson_id=context.persistence.lesson_version.lesson_id,
        session_id=context.session.id,
    )
    assert summary.availability == "paused"
    assert summary.can_start is False
    assert summary.latest is not None
    assert summary.active_attempt is not None

    attempt_count = await db_session.scalar(select(func.count()).select_from(AssessmentAttempt))
    with pytest.raises(APIError) as paused_start:
        await start_or_resume_interactive_attempt(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=context.session.id,
            lesson_id=context.persistence.lesson_version.lesson_id,
            presentation_locale="en",
            idempotency_key="paused-start",
            request_id=context.session.id,
            now=datetime.now(UTC),
        )
    assert paused_start.value.code == "ATTEMPT_NOT_WRITABLE"
    assert attempt_count == await db_session.scalar(
        select(func.count()).select_from(AssessmentAttempt)
    )

    with pytest.raises(APIError) as foreign:
        await get_lesson_interactive_training_summary(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            lesson_id=uuid4(),
            session_id=context.session.id,
        )
    assert foreign.value.status_code == 404
    assert foreign.value.code == "RESOURCE_NOT_FOUND"


@pytest.mark.integration
@pytest.mark.parametrize("assignment_status", ["in_progress", "completed"])
async def test_current_non_revoked_assignment_can_resume_practice(
    db_session: AsyncSession,
    assignment_status: str,
) -> None:
    context = await arrange_interactive_runtime(
        db_session,
        token_prefix="4" if assignment_status == "in_progress" else "5",
    )
    now = datetime.now(UTC)
    context.persistence.assignment.status = assignment_status
    context.persistence.assignment.started_at = now - timedelta(hours=1)
    if assignment_status == "completed":
        context.persistence.assignment.completed_at = now - timedelta(minutes=30)
    await db_session.flush()

    resumed = await start_or_resume_interactive_attempt(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        actor_user_id=context.employee_user.id,
        session_id=context.session.id,
        lesson_id=context.persistence.lesson_version.lesson_id,
        presentation_locale="en",
        idempotency_key=f"resume-{assignment_status}",
        request_id=context.session.id,
        now=now,
    )
    assert resumed.created is False
    assert resumed.attempt.id == context.attempt.id
    assert resumed.attempt.presentation_locale == "uk"

    first_question = resumed.attempt.questions[0]
    answer = await submit_interactive_answer(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        actor_user_id=context.employee_user.id,
        session_id=context.session.id,
        attempt_id=context.attempt.id,
        attempt_question_id=first_question.id,
        answer_payload=SingleChoiceSubmission(
            mechanic="single_choice",
            option_id=first_question.options[0].id,
        ),
        lease_generation=1,
        idempotency_key=f"answer-{assignment_status}",
        request_id=context.session.id,
        now=now,
    )
    assert answer.answer.is_correct is True
