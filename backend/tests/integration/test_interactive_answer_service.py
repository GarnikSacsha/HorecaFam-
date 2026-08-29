from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AttemptResult, OrganizationMembership, SubmittedAnswer
from app.schemas.assessment import SingleChoiceSubmission
from app.services.interactive_answers import submit_interactive_answer
from app.services.interactive_attempts import get_interactive_attempt, takeover_interactive_attempt
from tests.factories.auth import make_session
from tests.factories.interactive_training import arrange_interactive_runtime


@pytest.mark.integration
async def test_answers_are_idempotent_immediate_and_fifth_answer_completes_atomically(
    db_session: AsyncSession,
) -> None:
    context = await arrange_interactive_runtime(db_session)
    now = datetime.now(UTC)
    questions = context.start.attempt.questions

    first_payload = SingleChoiceSubmission(
        mechanic="single_choice",
        option_id=questions[0].options[0].id,
    )
    first = await submit_interactive_answer(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        actor_user_id=context.employee_user.id,
        session_id=context.session.id,
        attempt_id=context.attempt.id,
        attempt_question_id=questions[0].id,
        answer_payload=first_payload,
        lease_generation=1,
        idempotency_key="answer-1",
        request_id=context.session.id,
        now=now,
    )
    assert first.answer.is_correct is True
    assert first.feedback.is_correct is True
    assert first.feedback.correct_option_ids == [questions[0].options[0].id]
    assert first.next_question_id == questions[1].id
    assert first.result is None

    replay = await submit_interactive_answer(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        actor_user_id=context.employee_user.id,
        session_id=context.session.id,
        attempt_id=context.attempt.id,
        attempt_question_id=questions[0].id,
        answer_payload=first_payload,
        lease_generation=1,
        idempotency_key="answer-1",
        request_id=context.session.id,
        now=now,
    )
    assert replay.replayed is True
    assert replay.answer.id == first.answer.id

    with pytest.raises(APIError) as changed_key:
        await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=context.session.id,
            attempt_id=context.attempt.id,
            attempt_question_id=questions[0].id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=questions[0].options[1].id,
            ),
            lease_generation=1,
            idempotency_key="answer-1",
            request_id=context.session.id,
            now=now,
        )
    assert changed_key.value.code == "IDEMPOTENCY_KEY_REUSED"

    final_response = None
    for index, question in enumerate(questions[1:], start=1):
        selected = question.options[1].id if index == 2 else question.options[0].id
        final_response = await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=context.session.id,
            attempt_id=context.attempt.id,
            attempt_question_id=question.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=selected,
            ),
            lease_generation=1,
            idempotency_key=f"answer-{index + 1}",
            request_id=context.session.id,
            now=now,
        )
    assert final_response is not None
    assert final_response.attempt_status == "completed"
    assert final_response.next_question_id is None
    assert final_response.result is not None
    assert final_response.result.correct_count == 4
    assert final_response.result.score_basis_points == 8000
    assert final_response.result.knowledge_level == "strong"
    assert final_response.result.pass_status is None
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(SubmittedAnswer.attempt_id == context.attempt.id)
        )
        == 5
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AttemptResult)
            .where(AttemptResult.attempt_id == context.attempt.id)
        )
        == 1
    )

    resumed = await get_interactive_attempt(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        attempt_id=context.attempt.id,
        session_id=context.session.id,
    )
    assert all(question.answered for question in resumed.questions)
    assert all(question.confirmed_answer is not None for question in resumed.questions)
    assert all(question.feedback is not None for question in resumed.questions)


@pytest.mark.integration
async def test_pause_expiry_and_device_lease_block_answers_without_mutation(
    db_session: AsyncSession,
) -> None:
    context = await arrange_interactive_runtime(db_session, token_prefix="6")
    now = datetime.now(UTC)
    question = context.start.attempt.questions[0]
    second_session = make_session(
        context.employee_user,
        token_hash="8" * 64,
        csrf_token_hash="9" * 64,
    )
    db_session.add(second_session)
    await db_session.flush()
    takeover = await takeover_interactive_attempt(
        db_session,
        organization_id=context.persistence.assignment.organization_id,
        location_id=context.persistence.assignment.location_id,
        employee_profile_id=context.persistence.employee.id,
        actor_user_id=context.employee_user.id,
        session_id=second_session.id,
        attempt_id=context.attempt.id,
        idempotency_key="lease-takeover",
        request_id=second_session.id,
        now=now,
    )
    payload = SingleChoiceSubmission(mechanic="single_choice", option_id=question.options[0].id)
    with pytest.raises(APIError) as stale_lease:
        await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=context.session.id,
            attempt_id=context.attempt.id,
            attempt_question_id=question.id,
            answer_payload=payload,
            lease_generation=1,
            idempotency_key="stale-device-answer",
            request_id=context.session.id,
            now=now,
        )
    assert stale_lease.value.code == "ATTEMPT_DEVICE_CONFLICT"

    membership = await db_session.get(
        OrganizationMembership, context.persistence.employee.membership_id
    )
    assert membership is not None
    membership.training_participation_status = "paused"
    context.attempt.expires_at = context.attempt.started_at + timedelta(microseconds=1)
    await db_session.flush()
    with pytest.raises(APIError) as paused:
        await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=second_session.id,
            attempt_id=context.attempt.id,
            attempt_question_id=question.id,
            answer_payload=payload,
            lease_generation=takeover.lease_generation,
            idempotency_key="paused-answer",
            request_id=second_session.id,
            now=now,
        )
    assert paused.value.code == "ATTEMPT_NOT_WRITABLE"
    assert context.attempt.status == "in_progress"
    assert context.attempt.expires_at == now + timedelta(days=7)

    membership.training_participation_status = "active"
    context.attempt.expires_at = context.attempt.started_at + timedelta(microseconds=1)
    await db_session.flush()
    with pytest.raises(APIError) as expired:
        await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=second_session.id,
            attempt_id=context.attempt.id,
            attempt_question_id=question.id,
            answer_payload=payload,
            lease_generation=takeover.lease_generation,
            idempotency_key="expired-answer",
            request_id=second_session.id,
            now=now,
        )
    assert expired.value.code == "ATTEMPT_EXPIRED"
    assert context.attempt.status == "expired"
    assert await db_session.scalar(select(func.count()).select_from(SubmittedAnswer)) == 0


@pytest.mark.integration
async def test_fifth_answer_failure_rolls_back_answer_result_and_completion(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = await arrange_interactive_runtime(db_session, token_prefix="7")
    attempt_id = context.attempt.id
    questions = context.start.attempt.questions
    now = datetime.now(UTC)
    for index, question in enumerate(questions[:4]):
        await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=context.session.id,
            attempt_id=attempt_id,
            attempt_question_id=question.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=question.options[0].id,
            ),
            lease_generation=1,
            idempotency_key=f"rollback-answer-{index}",
            request_id=context.session.id,
            now=now,
        )

    from app.services import interactive_answers

    async def fail_completion(*_args: object, **_kwargs: object) -> AttemptResult:
        raise RuntimeError("forced result failure")

    monkeypatch.setattr(interactive_answers, "_complete_attempt", fail_completion)
    fifth = questions[4]
    with pytest.raises(RuntimeError, match="forced result failure"):
        await submit_interactive_answer(
            db_session,
            organization_id=context.persistence.assignment.organization_id,
            location_id=context.persistence.assignment.location_id,
            employee_profile_id=context.persistence.employee.id,
            actor_user_id=context.employee_user.id,
            session_id=context.session.id,
            attempt_id=attempt_id,
            attempt_question_id=fifth.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=fifth.options[0].id,
            ),
            lease_generation=1,
            idempotency_key="rollback-answer-5",
            request_id=context.session.id,
            now=now,
        )
    await db_session.rollback()
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(SubmittedAnswer.attempt_id == attempt_id)
        )
        == 4
    )
    assert await db_session.scalar(select(func.count()).select_from(AttemptResult)) == 0
    refreshed_attempt = await db_session.get(type(context.attempt), attempt_id)
    assert refreshed_attempt is not None
    assert refreshed_attempt.status == "in_progress"
