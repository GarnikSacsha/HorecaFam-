from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentQuestionPool,
    OrganizationMembership,
    QuestionOption,
    Session,
    User,
)
from app.services.interactive_attempts import (
    get_interactive_attempt,
    start_or_resume_interactive_attempt,
    takeover_interactive_attempt,
)
from tests.factories.assessments import (
    make_assessment_question_pool,
    make_assessment_readiness,
    make_question,
    make_question_option,
    make_question_version,
)
from tests.factories.auth import make_session
from tests.factories.training import make_lesson_completion
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.integration
async def test_attempt_snapshot_is_five_question_immutable_resumable_and_takeover_safe(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
    membership = await db_session.get(OrganizationMembership, context.employee.membership_id)
    assert membership is not None
    employee_user = await db_session.get(User, membership.user_id)
    assert employee_user is not None

    now = datetime.now(UTC)
    first_session = make_session(
        employee_user,
        token_hash="1" * 64,
        csrf_token_hash="2" * 64,
    )
    completion = make_lesson_completion(
        context.assignment,
        context.lesson_version,
        employee_user.id,
        completed_at=now,
    )
    db_session.add_all([first_session, completion])
    await db_session.flush()

    question_versions = [context.question_version]
    for index in range(1, 5):
        question = make_question(context.candidate)
        db_session.add(question)
        await db_session.flush()
        version = make_question_version(
            question,
            context.candidate,
            context.actor.id,
            prompt_payload={"text": f"Question {index}"},
            source_fingerprint=f"{index}" * 64,
        )
        db_session.add(version)
        await db_session.flush()
        question_versions.append(version)

    for index, version in enumerate(question_versions):
        db_session.add(
            make_assessment_question_pool(
                context.assessment_version,
                version,
                coverage_key=f"menu-item-{index}",
            )
        )
        db_session.add_all(
            [
                make_question_option(version, 0),
                make_question_option(version, 1),
            ]
        )
    db_session.add(
        make_assessment_readiness(
            context.assessment_version,
            status="warning",
            eligible_count=5,
        )
    )
    await db_session.flush()

    start = await start_or_resume_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=first_session.id,
        lesson_id=context.lesson_version.lesson_id,
        presentation_locale="uk",
        idempotency_key="attempt-start-1",
        request_id=first_session.id,
        now=now,
    )
    assert start.created is True
    assert start.replayed is False
    assert len(start.attempt.questions) == 5
    assert all(len(question.options) == 2 for question in start.attempt.questions)
    assert start.attempt.writable is True
    safe_json = start.attempt.model_dump_json()
    assert "grading_payload" not in safe_json
    assert "is_correct" not in safe_json
    assert "explanation_payload" not in safe_json

    replay = await start_or_resume_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=first_session.id,
        lesson_id=context.lesson_version.lesson_id,
        presentation_locale="uk",
        idempotency_key="attempt-start-1",
        request_id=first_session.id,
        now=now,
    )
    assert replay.replayed is True
    assert replay.attempt.id == start.attempt.id

    original_prompt = start.attempt.questions[0].prompt_payload
    question_versions[0].prompt_payload = {"text": "Changed after start"}
    source_option = await db_session.scalar(
        select(QuestionOption)
        .where(QuestionOption.question_version_id == question_versions[0].id)
        .limit(1)
    )
    assert source_option is not None
    source_option.payload = {"text": "Changed option"}
    await db_session.flush()
    immutable_read = await get_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        attempt_id=start.attempt.id,
        session_id=first_session.id,
    )
    assert immutable_read.questions[0].prompt_payload == original_prompt
    assert immutable_read.questions[0].options[0].payload != source_option.payload

    second_session = make_session(
        employee_user,
        token_hash="3" * 64,
        csrf_token_hash="4" * 64,
    )
    db_session.add(second_session)
    await db_session.flush()
    second_device = await start_or_resume_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=second_session.id,
        lesson_id=context.lesson_version.lesson_id,
        presentation_locale="en",
        idempotency_key="attempt-start-2",
        request_id=second_session.id,
        now=now,
    )
    assert second_device.created is False
    assert second_device.attempt.id == start.attempt.id
    assert second_device.attempt.presentation_locale == "uk"
    assert second_device.attempt.writable is False

    takeover = await takeover_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=second_session.id,
        attempt_id=start.attempt.id,
        idempotency_key="attempt-takeover-1",
        request_id=second_session.id,
        now=now,
    )
    assert takeover.lease_generation == 2
    assert takeover.replayed is False
    takeover_replay = await takeover_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=second_session.id,
        attempt_id=start.attempt.id,
        idempotency_key="attempt-takeover-1",
        request_id=second_session.id,
        now=now,
    )
    assert takeover_replay.lease_generation == 2
    assert takeover_replay.replayed is True

    stale_device = await get_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        attempt_id=start.attempt.id,
        session_id=first_session.id,
    )
    assert stale_device.writable is False
    current_device = await get_interactive_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        attempt_id=start.attempt.id,
        session_id=second_session.id,
    )
    assert current_device.writable is True
    assert (
        await db_session.scalar(
            select(AssessmentQuestionPool).where(
                AssessmentQuestionPool.assessment_version_id == context.assessment_version.id
            )
        )
        is not None
    )
    assert await db_session.get(Session, first_session.id) is not None
