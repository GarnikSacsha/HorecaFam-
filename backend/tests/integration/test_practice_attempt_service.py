import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import APIError
from app.db.session import create_engine, create_session_factory
from app.models import (
    AssessmentAttempt,
    AssessmentEligibility,
    AuditEvent,
    Organization,
    OrganizationMembership,
    User,
)
from app.schemas.assessment import PracticeFinishResponse, SingleChoiceSubmission
from app.services.practice_answers import save_practice_answer
from app.services.practice_attempts import (
    get_practice_attempt,
    get_practice_summary,
    start_or_resume_practice_attempt,
    takeover_practice_attempt,
)
from app.services.practice_results import finish_practice_attempt, get_practice_history
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
from tests.factories.identity import make_employee_profile, make_membership, make_user
from tests.integration.test_assessment_persistence import _make_context


async def _finish_in_independent_session(
    session_factory: async_sessionmaker[AsyncSession],
    **kwargs: Any,
) -> PracticeFinishResponse | Exception:
    async with session_factory() as session:
        try:
            return await finish_practice_attempt(session, **kwargs)
        except Exception as exception:
            return exception


@pytest.mark.integration
async def test_practice_start_resume_snapshot_and_takeover_are_tenant_safe(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    context = await _make_context(db_session)
    membership = await db_session.get(OrganizationMembership, context.employee.membership_id)
    assert membership is not None
    employee_user = await db_session.get(User, membership.user_id)
    assert employee_user is not None
    organization_id = context.assignment.organization_id
    location_id = context.assignment.location_id
    employee_profile_id = context.employee.id
    employee_user_id = employee_user.id
    assignment_id = context.assignment.id
    now = datetime.now(UTC)

    practice = make_assessment(
        context.training,
        None,
        assessment_type="whole_menu_knowledge_check",
    )
    final_exam = make_assessment(
        context.training,
        None,
        assessment_type="menu_final_exam",
    )
    db_session.add_all([practice, final_exam])
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
    first_session_id = first_session.id

    context.question_version.is_critical = True
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

    incomplete_summary = await get_practice_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        session_id=first_session.id,
    )
    assert incomplete_summary.availability == "training_incomplete"
    assert incomplete_summary.reason_codes == ["TRAINING_INCOMPLETE"]

    organization = await db_session.get(Organization, organization_id)
    assert organization is not None
    unassigned_user = make_user(email_normalized="practice-unassigned@example.com")
    unassigned_membership = make_membership(organization, unassigned_user)
    unassigned_employee = make_employee_profile(
        unassigned_membership,
        organization_id,
        location_id=location_id,
    )
    db_session.add_all([unassigned_user, unassigned_membership, unassigned_employee])
    await db_session.flush()
    unassigned_summary = await get_practice_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=unassigned_employee.id,
        session_id=first_session.id,
    )
    assert unassigned_summary.availability == "no_assignment"
    assert unassigned_summary.reason_codes == ["ASSIGNMENT_UNAVAILABLE"]

    context.assignment.status = "completed"
    context.assignment.started_at = now
    context.assignment.completed_at = now
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
            session_id=first_session_id,
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
    second_session_id = second_session.id
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

    finish_kwargs = dict(
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=second_session.id,
        attempt_id=started.attempt.id,
        lease_generation=2,
        idempotency_key="practice-finish-1",
        request_id=second_session.id,
        now=now + timedelta(minutes=1),
    )
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        same_key_outcomes = await asyncio.gather(
            _finish_in_independent_session(session_factory, **finish_kwargs),
            _finish_in_independent_session(session_factory, **finish_kwargs),
        )
    finally:
        await engine.dispose()
    assert all(isinstance(outcome, PracticeFinishResponse) for outcome in same_key_outcomes)
    same_key_responses = [
        outcome for outcome in same_key_outcomes if isinstance(outcome, PracticeFinishResponse)
    ]
    assert {response.replayed for response in same_key_responses} == {False, True}
    finished = next(response for response in same_key_responses if not response.replayed)
    assert finished.result.correct_count == 10
    assert finished.result.total_count == 10
    assert finished.result.score_basis_points == 10000
    assert finished.result.knowledge_level == "strong"
    assert finished.result.pass_status is None
    assert finished.result.critical_error_count == 0
    assert finished.qualified is True
    assert finished.eligibility_earned is True
    assert finished.replayed is False
    assert len(finished.review) == 10
    assert all(item.is_correct for item in finished.review)
    revealed_json = finished.model_dump_json()
    assert "correct_option_ids" in revealed_json
    assert "explanation_payload" in revealed_json
    assert "grading_payload" not in revealed_json
    assert "provenance" not in revealed_json
    await db_session.rollback()
    finish_replay = await finish_practice_attempt(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=employee_user_id,
        session_id=second_session_id,
        attempt_id=started.attempt.id,
        lease_generation=2,
        idempotency_key="practice-finish-1",
        request_id=second_session_id,
        now=now + timedelta(minutes=1),
    )
    assert finish_replay.replayed is True
    assert finish_replay.result.id == finished.result.id

    replacement = await start_or_resume_practice_attempt(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=employee_user_id,
        session_id=second_session_id,
        presentation_locale="uk",
        idempotency_key="practice-start-after-finish",
        request_id=second_session_id,
        now=now + timedelta(minutes=2),
    )
    assert replacement.created is True
    assert replacement.attempt.id != started.attempt.id
    with pytest.raises(APIError) as device_conflict:
        await save_practice_answer(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=employee_user_id,
            session_id=first_session_id,
            attempt_id=replacement.attempt.id,
            attempt_question_id=replacement.attempt.questions[0].id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=replacement.attempt.questions[0].options[1].id,
            ),
            lease_generation=1,
            idempotency_key="practice-answer-stale-device",
            request_id=second_session_id,
            now=now + timedelta(minutes=2),
        )
    assert device_conflict.value.code == "ATTEMPT_DEVICE_CONFLICT"

    for index, attempt_question in enumerate(replacement.attempt.questions):
        await save_practice_answer(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=employee_user_id,
            session_id=second_session_id,
            attempt_id=replacement.attempt.id,
            attempt_question_id=attempt_question.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice", option_id=attempt_question.options[1].id
            ),
            lease_generation=1,
            idempotency_key=f"practice-retry-answer-{index}",
            request_id=second_session_id,
            now=now + timedelta(minutes=2),
        )
    weak_finish_kwargs = dict(
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=employee_user_id,
        session_id=second_session_id,
        attempt_id=replacement.attempt.id,
        lease_generation=1,
        request_id=second_session_id,
        now=now + timedelta(minutes=3),
    )
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        different_key_outcomes = await asyncio.gather(
            _finish_in_independent_session(
                session_factory,
                **weak_finish_kwargs,
                idempotency_key="practice-finish-2-a",
            ),
            _finish_in_independent_session(
                session_factory,
                **weak_finish_kwargs,
                idempotency_key="practice-finish-2-b",
            ),
        )
    finally:
        await engine.dispose()
    weak_responses = [
        outcome for outcome in different_key_outcomes if isinstance(outcome, PracticeFinishResponse)
    ]
    weak_conflicts = [
        outcome for outcome in different_key_outcomes if isinstance(outcome, APIError)
    ]
    assert len(weak_responses) == 1
    assert len(weak_conflicts) == 1
    assert weak_conflicts[0].code == "ATTEMPT_ALREADY_COMPLETED"
    weaker = weak_responses[0]
    await db_session.rollback()
    assert weaker.result.correct_count == 0
    assert weaker.result.knowledge_level == "very_weak"
    assert weaker.result.critical_error_count == 1
    assert weaker.qualified is True
    assert weaker.eligibility_earned is False

    history = await get_practice_history(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    assert history.qualified is True
    assert history.latest is not None and history.latest.attempt_id == replacement.attempt.id
    assert history.best is not None and history.best.attempt_id == started.attempt.id
    assert [item.attempt_id for item in history.history] == [
        replacement.attempt.id,
        started.attempt.id,
    ]
    assert (
        len(
            list(
                await db_session.scalars(
                    select(AssessmentEligibility).where(
                        AssessmentEligibility.employee_profile_id == employee_profile_id,
                        AssessmentEligibility.assignment_id == assignment_id,
                        AssessmentEligibility.status == "earned",
                    )
                )
            )
        )
        == 1
    )

    completed_summary = await get_practice_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        session_id=second_session_id,
    )
    assert completed_summary.qualified is True
    assert completed_summary.latest is not None
    assert completed_summary.latest.attempt_id == replacement.attempt.id
    assert completed_summary.best is not None
    assert completed_summary.best.attempt_id == started.attempt.id


@pytest.mark.parametrize(
    ("state", "availability", "error"),
    [
        ("incomplete", "training_incomplete", "PRACTICE_UNAVAILABLE"),
        ("no_version", "preparing", "ASSESSMENT_NOT_READY"),
        ("blocked", "preparing", "ASSESSMENT_NOT_READY"),
        ("processing", "preparing", "ASSESSMENT_NOT_READY"),
        ("no_assignment", "no_assignment", "RESOURCE_NOT_FOUND"),
        ("paused", "paused", "ATTEMPT_NOT_WRITABLE"),
    ],
)
async def test_practice_prerequisites_preserve_empty_attempt_history(
    db_session: AsyncSession, state: str, availability: str, error: str
) -> None:
    context = await _make_context(db_session)
    now = datetime.now(UTC)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    session = make_session(user, token_hash="7" * 64, csrf_token_hash="8" * 64)
    db_session.add(session)
    if state != "incomplete":
        context.assignment.status = "completed"
        context.assignment.started_at = context.assignment.completed_at = now
    if state == "no_assignment":
        context.assignment.status = "revoked"
        context.assignment.revoked_at = now
        context.assignment.revoke_reason = "admin"
    elif state == "paused":
        membership.training_participation_status = "paused"
        membership.training_paused_at = now
        membership.training_pause_reason_code = "leave"
    if state in {"blocked", "processing"}:
        assessment = make_assessment(
            context.training, None, assessment_type="whole_menu_knowledge_check"
        )
        db_session.add(assessment)
        await db_session.flush()
        version = make_assessment_version(
            assessment,
            context.training_version,
            None,
            question_count=10,
            threshold_percent=40,
            feedback_policy="after_final_submission",
        )
        db_session.add(version)
        await db_session.flush()
        db_session.add(
            make_assessment_readiness(version, status=state, eligible_count=0, required_count=10)
        )
    await db_session.commit()
    org_id, location_id, employee_id = (
        context.assignment.organization_id,
        context.assignment.location_id,
        context.employee.id,
    )
    session_id, user_id = session.id, user.id
    summary = await get_practice_summary(
        db_session,
        organization_id=org_id,
        location_id=location_id,
        employee_profile_id=employee_id,
        session_id=session_id,
    )
    assert summary.availability == availability and summary.can_start is False
    assert summary.active_attempt is None and summary.latest is None and summary.best is None
    with pytest.raises(APIError, match=error):
        await start_or_resume_practice_attempt(
            db_session,
            organization_id=org_id,
            location_id=location_id,
            employee_profile_id=employee_id,
            actor_user_id=user_id,
            session_id=session_id,
            presentation_locale="uk",
            idempotency_key="denied-start",
            request_id=uuid4(),
            now=now,
        )
    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(AssessmentAttempt)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


@pytest.mark.parametrize("operation", ["answer", "finish"])
@pytest.mark.parametrize(
    ("state", "error"),
    [
        ("disabled", "ATTEMPT_NOT_WRITABLE"),
        ("paused", "ATTEMPT_NOT_WRITABLE"),
        ("revoked", "ATTEMPT_NOT_WRITABLE"),
        ("completed", "ATTEMPT_ALREADY_COMPLETED"),
        ("expired", "ATTEMPT_EXPIRED"),
        ("invalidated", "ATTEMPT_NOT_WRITABLE"),
        ("lease", "ATTEMPT_DEVICE_CONFLICT"),
    ],
)
async def test_practice_write_guards_preserve_answers_results_and_audit(
    db_session: AsyncSession, operation: str, state: str, error: str
) -> None:
    from app.models import AttemptResult, SubmittedAnswer
    from tests.factories.assessments import (
        make_assessment_attempt,
        make_attempt_device_lease,
        make_attempt_question,
    )

    context = await _make_context(db_session)
    now = datetime.now(UTC)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    context.assignment.status = "completed"
    context.assignment.started_at = context.assignment.completed_at = now
    exam = make_assessment(context.training, None, assessment_type="whole_menu_knowledge_check")
    db_session.add(exam)
    await db_session.flush()
    version = make_assessment_version(
        exam,
        context.training_version,
        None,
        question_count=10,
        threshold_percent=40,
        feedback_policy="after_final_submission",
    )
    session = make_session(user, token_hash="b" * 64, csrf_token_hash="c" * 64)
    db_session.add_all([version, session])
    await db_session.flush()
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        version,
        question_count=10,
        started_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(attempt)
    await db_session.flush()
    question = make_attempt_question(attempt, context.question_version)
    db_session.add_all([question, make_attempt_device_lease(attempt, session)])
    if state == "disabled":
        membership.status = "disabled"
        membership.disabled_at = now
        membership.disabled_reason_code = "leave"
    elif state == "paused":
        membership.training_participation_status = "paused"
        membership.training_paused_at = now
        membership.training_pause_reason_code = "leave"
    elif state == "revoked":
        context.assignment.status = "revoked"
        context.assignment.revoked_at = now
        context.assignment.revoke_reason = "admin"
    elif state == "completed":
        attempt.status = "completed"
        attempt.completed_at = now
    elif state == "expired":
        attempt.started_at = now - timedelta(days=7)
        attempt.last_activity_at = now - timedelta(days=7)
        attempt.expires_at = now
    elif state == "invalidated":
        attempt.status = "invalidated"
        attempt.invalidation_code = "ASSIGNMENT_REVOKED"
    await db_session.commit()
    args: dict[str, Any] = dict(
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=user.id,
        session_id=session.id,
        attempt_id=attempt.id,
        lease_generation=2 if state == "lease" else 1,
        idempotency_key=f"guard-{operation}-{state}",
        request_id=uuid4(),
        now=now,
    )
    question_id, attempt_id = question.id, attempt.id
    models = (SubmittedAnswer, AttemptResult, AuditEvent)
    before = [await db_session.scalar(select(func.count()).select_from(model)) for model in models]
    with pytest.raises(APIError, match=error):
        if operation == "answer":
            await save_practice_answer(
                db_session,
                **args,
                attempt_question_id=question_id,
                answer_payload=SingleChoiceSubmission(mechanic="single_choice", option_id=uuid4()),
            )
        else:
            await finish_practice_attempt(db_session, **args)
    await db_session.rollback()
    assert [
        await db_session.scalar(select(func.count()).select_from(model)) for model in models
    ] == before
    stored = await db_session.get_one(AssessmentAttempt, attempt_id)
    if state == "expired":
        assert stored.status == "expired"
        assert stored.invalidation_code == "INACTIVITY_TIMEOUT"
    elif state == "paused":
        assert stored.status == "in_progress"
        assert stored.expires_at == now + timedelta(days=7)


@pytest.mark.parametrize("state", ["active", "completed", "expired", "missing"])
async def test_practice_takeover_preserves_terminal_state_and_replays_once(
    db_session: AsyncSession,
    state: str,
) -> None:
    from app.models import AttemptDeviceLease
    from app.services.practice_attempts import takeover_practice_attempt
    from tests.factories.assessments import make_assessment_attempt, make_attempt_device_lease

    context = await _make_context(db_session)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    now = datetime.now(UTC)
    exam = make_assessment(context.training, None, assessment_type="whole_menu_knowledge_check")
    db_session.add(exam)
    await db_session.flush()
    version = make_assessment_version(
        exam,
        context.training_version,
        None,
        question_count=10,
        threshold_percent=40,
        feedback_policy="after_final_submission",
    )
    session = make_session(user, token_hash="e" * 64, csrf_token_hash="f" * 64)
    db_session.add_all([version, session])
    await db_session.flush()
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        version,
        question_count=10,
        started_at=now - timedelta(days=7),
        last_activity_at=now - timedelta(days=7),
        expires_at=now if state == "expired" else now + timedelta(days=1),
        status="completed" if state == "completed" else "in_progress",
        completed_at=now if state == "completed" else None,
    )
    lease = make_attempt_device_lease(attempt, session)
    db_session.add_all([attempt, lease])
    await db_session.commit()
    lease_id = lease.id
    args: dict[str, Any] = dict(
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=user.id,
        session_id=session.id,
        attempt_id=uuid4() if state == "missing" else attempt.id,
        idempotency_key="takeover-once",
        request_id=uuid4(),
        now=now,
    )
    if state == "active":
        first = await takeover_practice_attempt(db_session, **args)
        assert first.lease_generation == 2 and not first.replayed
        before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
        replay = await takeover_practice_attempt(db_session, **args)
        assert replay.lease_generation == 2 and replay.replayed
        assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
    else:
        error = {
            "completed": "ATTEMPT_ALREADY_COMPLETED",
            "expired": "ATTEMPT_EXPIRED",
            "missing": "RESOURCE_NOT_FOUND",
        }[state]
        before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
        with pytest.raises(APIError, match=error):
            await takeover_practice_attempt(db_session, **args)
        await db_session.rollback()
        assert (await db_session.get_one(AttemptDeviceLease, lease_id)).generation == 1
        assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
