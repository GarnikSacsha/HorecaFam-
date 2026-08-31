from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import OrganizationMembership, User
from app.schemas.assessment import SingleChoiceSubmission
from app.services.practice_answers import save_practice_answer
from app.services.practice_attempts import (
    get_practice_attempt,
    get_practice_summary,
    start_or_resume_practice_attempt,
    takeover_practice_attempt,
)
from tests.factories.assessments import (
    make_assessment,
    make_assessment_question_pool,
    make_assessment_readiness,
    make_assessment_version,
    make_question,
    make_question_option,
    make_question_version,
)
from tests.factories.auth import make_session
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.integration
async def test_practice_start_resume_snapshot_and_takeover_are_tenant_safe(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
    membership = await db_session.get(OrganizationMembership, context.employee.membership_id)
    assert membership is not None
    employee_user = await db_session.get(User, membership.user_id)
    assert employee_user is not None
    now = datetime.now(UTC)
    context.assignment.status = "completed"
    context.assignment.started_at = now
    context.assignment.completed_at = now

    practice = make_assessment(
        context.training,
        None,
        assessment_type="whole_menu_knowledge_check",
    )
    db_session.add(practice)
    await db_session.flush()
    practice_version = make_assessment_version(
        practice,
        context.training_version,
        None,
        question_count=10,
        threshold_percent=40,
        feedback_policy="after_final_submission",
    )
    first_session = make_session(
        employee_user,
        token_hash="5" * 64,
        csrf_token_hash="6" * 64,
    )
    db_session.add_all([practice_version, first_session])
    await db_session.flush()

    question_versions = [context.question_version]
    for index in range(1, 10):
        question = make_question(context.candidate)
        db_session.add(question)
        await db_session.flush()
        version = make_question_version(
            question,
            context.candidate,
            context.actor.id,
            prompt_payload={"text": f"Practice question {index}"},
            source_fingerprint=f"{index}" * 64,
        )
        db_session.add(version)
        await db_session.flush()
        question_versions.append(version)
    for index, version in enumerate(question_versions):
        db_session.add(
            make_assessment_question_pool(
                practice_version,
                version,
                coverage_key=f"menu_item:{index}",
            )
        )
        db_session.add_all([make_question_option(version, 0), make_question_option(version, 1)])
    db_session.add(
        make_assessment_readiness(
            practice_version,
            status="warning",
            eligible_count=10,
            required_count=10,
        )
    )
    await db_session.flush()

    summary = await get_practice_summary(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        session_id=first_session.id,
    )
    assert summary.availability == "ready"
    assert summary.can_start is True

    started = await start_or_resume_practice_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=first_session.id,
        presentation_locale="uk",
        idempotency_key="practice-start-1",
        request_id=first_session.id,
        now=now,
    )
    assert started.created is True
    assert len(started.attempt.questions) == 10
    assert len({question.coverage_key for question in started.attempt.questions}) == 10
    safe_json = started.attempt.model_dump_json()
    assert "grading_payload" not in safe_json
    assert "is_correct" not in safe_json
    assert "explanation_payload" not in safe_json
    assert "provenance" not in safe_json

    replay = await start_or_resume_practice_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=first_session.id,
        presentation_locale="uk",
        idempotency_key="practice-start-1",
        request_id=first_session.id,
        now=now,
    )
    assert replay.replayed is True
    assert replay.attempt.id == started.attempt.id

    for index, attempt_question in enumerate(started.attempt.questions):
        answer = await save_practice_answer(
            db_session,
            organization_id=context.assignment.organization_id,
            location_id=context.assignment.location_id,
            employee_profile_id=context.employee.id,
            actor_user_id=employee_user.id,
            session_id=first_session.id,
            attempt_id=started.attempt.id,
            attempt_question_id=attempt_question.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice", option_id=attempt_question.options[0].id
            ),
            lease_generation=1,
            idempotency_key=f"practice-answer-{index}",
            request_id=first_session.id,
            now=now,
        )
        assert answer.attempt_status == "in_progress"
        safe_answer = answer.model_dump_json()
        assert "is_correct" not in safe_answer
        assert "correct_option" not in safe_answer
        assert "explanation" not in safe_answer
        assert "grading" not in safe_answer
        assert "provenance" not in safe_answer
    answer_replay = await save_practice_answer(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=first_session.id,
        attempt_id=started.attempt.id,
        attempt_question_id=started.attempt.questions[0].id,
        answer_payload=SingleChoiceSubmission(
            mechanic="single_choice",
            option_id=started.attempt.questions[0].options[0].id,
        ),
        lease_generation=1,
        idempotency_key="practice-answer-0",
        request_id=first_session.id,
        now=now,
    )
    assert answer_replay.replayed is True
    assert answer_replay.answered_count == 10

    second_session = make_session(
        employee_user,
        token_hash="7" * 64,
        csrf_token_hash="8" * 64,
    )
    db_session.add(second_session)
    await db_session.flush()
    second_device = await get_practice_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        attempt_id=started.attempt.id,
        session_id=second_session.id,
    )
    assert second_device.writable is False

    takeover = await takeover_practice_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=second_session.id,
        attempt_id=started.attempt.id,
        idempotency_key="practice-takeover-1",
        request_id=second_session.id,
        now=now,
    )
    assert takeover.lease_generation == 2
    assert takeover.replayed is False

    replacement = await start_or_resume_practice_attempt(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=second_session.id,
        presentation_locale="uk",
        idempotency_key="practice-start-after-expiry",
        request_id=second_session.id,
        now=now + timedelta(days=8),
    )
    assert replacement.created is True
    assert replacement.attempt.id != started.attempt.id
    with pytest.raises(APIError) as device_conflict:
        await save_practice_answer(
            db_session,
            organization_id=context.assignment.organization_id,
            location_id=context.assignment.location_id,
            employee_profile_id=context.employee.id,
            actor_user_id=employee_user.id,
            session_id=first_session.id,
            attempt_id=replacement.attempt.id,
            attempt_question_id=replacement.attempt.questions[0].id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=replacement.attempt.questions[0].options[0].id,
            ),
            lease_generation=1,
            idempotency_key="practice-answer-stale-device",
            request_id=first_session.id,
            now=now + timedelta(days=8),
        )
    assert device_conflict.value.code == "ATTEMPT_DEVICE_CONFLICT"
