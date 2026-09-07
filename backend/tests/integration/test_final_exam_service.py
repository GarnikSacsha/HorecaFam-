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
    AttemptResult,
    AttentionCase,
    AuditEvent,
    OrganizationMembership,
    RetakeRequirement,
    User,
)
from app.schemas.assessment import FinalExamFinishResponse, SingleChoiceSubmission
from app.services.admin_results import (
    get_admin_employee_results,
    get_admin_final_exam_result,
    get_admin_results_overview,
)
from app.services.final_exam_answers import save_final_exam_answer
from app.services.final_exam_attempts import (
    get_final_exam_attempt,
    get_final_exam_summary,
    start_or_resume_final_exam_attempt,
)
from app.services.final_exam_results import finish_final_exam_attempt, get_final_exam_history
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_eligibility,
    make_assessment_readiness,
    make_assessment_version,
    make_attempt_device_lease,
    make_attempt_option,
    make_attempt_question,
    make_question,
    make_question_candidate,
    make_question_option,
    make_question_version,
)
from tests.factories.auth import make_session
from tests.integration.test_assessment_persistence import _make_context


async def _finish_in_independent_session(
    session_factory: async_sessionmaker[AsyncSession],
    **kwargs: Any,
) -> FinalExamFinishResponse | Exception:
    async with session_factory() as session:
        try:
            return await finish_final_exam_attempt(session, **kwargs)
        except Exception as exception:
            return exception


@pytest.mark.integration
@pytest.mark.parametrize(
    ("state", "availability", "error"),
    [
        ("incomplete", "training_incomplete", "TRAINING_INCOMPLETE"),
        ("no_version", "preparing", "ASSESSMENT_NOT_READY"),
        ("blocked", "practice_required", "ASSESSMENT_NOT_READY"),
        ("no_eligibility", "practice_required", "PRACTICE_ELIGIBILITY_REQUIRED"),
        ("no_assignment", "no_assignment", "RESOURCE_NOT_FOUND"),
        ("paused", "paused", "ATTEMPT_NOT_WRITABLE"),
    ],
)
async def test_final_exam_preconditions_reject_start_without_new_history(
    db_session: AsyncSession, state: str, availability: str, error: str
) -> None:
    context = await _make_context(db_session)
    now = datetime.now(UTC)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    session = make_session(user, token_hash="c" * 64, csrf_token_hash="d" * 64)
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
    if state in {"blocked", "no_eligibility"}:
        exam = make_assessment(context.training, None, assessment_type="menu_final_exam")
        db_session.add(exam)
        await db_session.flush()
        version = make_assessment_version(
            exam,
            context.training_version,
            None,
            question_count=20,
            threshold_percent=70,
            feedback_policy="after_final_submission",
        )
        db_session.add(version)
        await db_session.flush()
        db_session.add(
            make_assessment_readiness(
                version,
                status="blocked" if state == "blocked" else "ready",
                eligible_count=0 if state == "blocked" else 20,
                required_count=20,
            )
        )
    await db_session.commit()
    organization_id, location_id = (
        context.assignment.organization_id,
        context.assignment.location_id,
    )
    employee_id, user_id, session_id = context.employee.id, user.id, session.id
    summary = await get_final_exam_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_id,
        session_id=session_id,
        now=now,
    )
    assert summary.availability == availability and summary.can_start is False
    assert summary.active_attempt is None and summary.certification is None
    counts = [
        await db_session.scalar(select(func.count()).select_from(model))
        for model in (AssessmentAttempt, AttemptResult, AuditEvent)
    ]
    with pytest.raises(APIError, match=error):
        await start_or_resume_final_exam_attempt(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_id,
            actor_user_id=user_id,
            session_id=session_id,
            presentation_locale="uk",
            idempotency_key="denied-final-start",
            request_id=uuid4(),
            now=now,
        )
    await db_session.rollback()
    assert [
        await db_session.scalar(select(func.count()).select_from(model))
        for model in (AssessmentAttempt, AttemptResult, AuditEvent)
    ] == counts


@pytest.mark.integration
async def test_final_exam_grades_once_certifies_and_exposes_canonical_results(
    db_session: AsyncSession,
    migrated_test_database: Settings,
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

    final_exam = make_assessment(
        context.training,
        None,
        assessment_type="menu_final_exam",
    )
    db_session.add(final_exam)
    await db_session.flush()
    final_exam_version = make_assessment_version(
        final_exam,
        context.training_version,
        None,
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
    )
    db_session.add(final_exam_version)
    await db_session.flush()
    db_session.add(
        make_assessment_readiness(
            final_exam_version,
            status="warning",
            eligible_count=20,
            required_count=20,
            warning_codes=["REPEAT_ROTATION_LIMITED"],
        )
    )

    qualifying_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        context.assessment_version,
        status="completed",
        question_count=5,
        completed_at=now,
    )
    db_session.add(qualifying_attempt)
    await db_session.flush()
    db_session.add(
        make_assessment_eligibility(
            context.employee,
            context.assignment,
            final_exam,
            qualifying_attempt,
            earned_at=now,
        )
    )

    employee_session = make_session(
        employee_user,
        token_hash="9" * 64,
        csrf_token_hash="a" * 64,
    )
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        question_count=20,
        started_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add_all([employee_session, attempt])
    await db_session.flush()
    db_session.add(make_attempt_device_lease(attempt, employee_session))

    question_versions = [context.question_version]
    for index in range(1, 20):
        candidate = make_question_candidate(
            context.rule,
            context.training_version,
            context.lesson_version,
            prompt_payload={"text": f"Final Exam question {index + 1}"},
            source_fingerprint=f"{index:064x}",
            status="approved",
        )
        question = make_question(candidate)
        db_session.add_all([candidate, question])
        await db_session.flush()
        question_version = make_question_version(
            question,
            candidate,
            context.actor.id,
        )
        db_session.add(question_version)
        await db_session.flush()
        question_versions.append(question_version)

    attempt_questions = []
    for index, question_version in enumerate(question_versions):
        source_options = [
            make_question_option(question_version, 0),
            make_question_option(question_version, 1),
        ]
        db_session.add_all(source_options)
        await db_session.flush()
        attempt_question = make_attempt_question(
            attempt,
            question_version,
            position=index,
            coverage_key=f"menu-item-{index + 1}",
            is_critical=index == 19,
        )
        db_session.add(attempt_question)
        await db_session.flush()
        db_session.add_all(
            [
                make_attempt_option(attempt_question, source_options[0]),
                make_attempt_option(attempt_question, source_options[1]),
            ]
        )
        attempt_questions.append(attempt_question)
    await db_session.commit()

    organization_id = context.assignment.organization_id
    location_id = context.assignment.location_id
    employee_profile_id = context.employee.id
    actor_user_id = employee_user.id
    session_id = employee_session.id
    attempt_id = attempt.id
    training_id = context.training.id
    assignment_id = context.assignment.id
    final_exam_id = final_exam.id
    admin_user_id = context.actor.id

    summary = await get_final_exam_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        session_id=session_id,
    )
    assert summary.availability == "in_progress"
    assert summary.active_attempt is not None
    assert len(summary.active_attempt.questions) == 20
    safe_attempt = summary.active_attempt.model_dump_json()
    assert "grading_payload" not in safe_attempt
    assert "explanation_payload" not in safe_attempt
    assert "is_correct" not in safe_attempt

    direct_attempt = await get_final_exam_attempt(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        session_id=session_id,
    )
    assert direct_attempt.writable is True

    for expected_replay in (False, True):
        resumed = await start_or_resume_final_exam_attempt(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            presentation_locale="uk",
            idempotency_key="resume-existing-final",
            request_id=uuid4(),
            now=now,
        )
        assert resumed.attempt.id == attempt_id and resumed.created is False
        assert resumed.replayed is expected_replay

    for index, attempt_question_response in enumerate(direct_attempt.questions):
        chosen = attempt_question_response.options[0 if index < 14 else 1]
        answer = await save_final_exam_answer(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            attempt_id=attempt_id,
            attempt_question_id=attempt_question_response.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=chosen.id,
            ),
            lease_generation=1,
            idempotency_key=f"final-exam-answer-{index}",
            request_id=session_id,
            now=now + timedelta(minutes=index + 1),
        )
        answer_json = answer.model_dump_json()
        assert "feedback" not in answer_json
        assert "is_correct" not in answer_json
        assert "explanation" not in answer_json
    assert answer.answered_count == 20

    saved_attempt = await get_final_exam_attempt(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        session_id=session_id,
    )
    assert saved_attempt.answered_count == 20
    assert all(question.saved_answer is not None for question in saved_attempt.questions)
    assert "is_correct" not in saved_attempt.model_dump_json()

    finish_kwargs = dict(
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        attempt_id=attempt_id,
        lease_generation=1,
        idempotency_key="final-exam-finish",
        request_id=session_id,
        now=now + timedelta(minutes=30),
    )
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        outcomes = await asyncio.gather(
            _finish_in_independent_session(session_factory, **finish_kwargs),
            _finish_in_independent_session(session_factory, **finish_kwargs),
        )
    finally:
        await engine.dispose()
    responses = [outcome for outcome in outcomes if isinstance(outcome, FinalExamFinishResponse)]
    assert len(responses) == 2
    assert {response.replayed for response in responses} == {False, True}
    finished = next(response for response in responses if not response.replayed)
    await db_session.rollback()
    assert finished.result.correct_count == 14
    assert finished.result.total_count == 20
    assert finished.result.score_basis_points == 7000
    assert finished.result.pass_status == "passed"
    assert finished.result.critical_error_count == 1
    assert finished.certification is not None
    assert finished.newly_certified is True
    assert finished.retake_available is False
    assert len(finished.review) == 20
    assert "correct_option_ids" in finished.model_dump_json()

    replay = await finish_final_exam_attempt(db_session, **finish_kwargs)
    assert replay.replayed is True
    assert replay.result.id == finished.result.id

    history = await get_final_exam_history(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    assert history.certification is not None
    assert history.latest is not None and history.latest.pass_status == "passed"
    assert history.best is not None and history.best.result_id == finished.result.id
    assert len(history.history) == 1

    certified_summary = await get_final_exam_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        session_id=session_id,
    )
    assert certified_summary.availability == "certified"
    assert certified_summary.can_start is False
    assert certified_summary.retake_available is False

    authorized_requirement = RetakeRequirement(
        organization_id=organization_id,
        location_id=location_id,
        training_id=training_id,
        employee_profile_id=employee_profile_id,
        assignment_id=assignment_id,
        target_assessment_id=final_exam_id,
        reason="management_follow_up",
        state="active",
        management_source_key="certified-follow-up",
        target_policy={"assessment_type": "menu_final_exam", "minimum_result": "passed"},
        confirmed_at=now + timedelta(minutes=31),
        confirmed_by_user_id=admin_user_id,
        due_at=now + timedelta(days=7),
        revision=0,
    )
    db_session.add(authorized_requirement)
    await db_session.commit()
    authorized_summary = await get_final_exam_summary(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        session_id=session_id,
        now=now + timedelta(minutes=32),
    )
    assert authorized_summary.availability == "eligible"
    assert authorized_summary.can_start is True
    assert authorized_summary.reason_codes == ["AUTHORIZED_RETAKE"]
    assert authorized_summary.current_retake_requirement is not None
    assert authorized_summary.current_retake_requirement.id == authorized_requirement.id

    authorized_requirement.state = "cancelled"
    authorized_requirement.cancelled_at = now + timedelta(minutes=33)
    authorized_requirement.cancelled_by_user_id = admin_user_id
    authorized_requirement.cancellation_comment = "Use a targeted critical follow-up instead."
    critical_case = AttentionCase(
        organization_id=organization_id,
        location_id=location_id,
        training_id=training_id,
        employee_profile_id=employee_profile_id,
        case_type="critical_allergen",
        subject_key=f"menu_item:{uuid4()}:allergen:{uuid4()}",
        state="open",
        revision=0,
        created_at=now + timedelta(minutes=34),
        updated_at=now + timedelta(minutes=34),
    )
    db_session.add(critical_case)
    await db_session.flush()
    critical_requirement = RetakeRequirement(
        organization_id=organization_id,
        location_id=location_id,
        training_id=training_id,
        employee_profile_id=employee_profile_id,
        assignment_id=assignment_id,
        target_assessment_id=final_exam_id,
        reason="critical_error",
        state="active",
        source_attention_case_id=critical_case.id,
        target_policy={
            "assessment_type": "menu_final_exam",
            "minimum_result": "passed",
            "required_subject_keys": [critical_case.subject_key],
        },
        confirmed_at=now + timedelta(minutes=34),
        confirmed_by_user_id=admin_user_id,
        due_at=now + timedelta(days=7),
        revision=0,
    )
    db_session.add(critical_requirement)
    await db_session.commit()
    with pytest.raises(APIError) as unavailable:
        await start_or_resume_final_exam_attempt(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            presentation_locale="uk",
            idempotency_key="critical-target-unavailable",
            request_id=session_id,
            now=now + timedelta(minutes=35),
        )
    assert unavailable.value.code == "RETAKE_TARGET_UNAVAILABLE"

    overview = await get_admin_results_overview(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    employee_row = next(item for item in overview.items if item.employee_id == employee_profile_id)
    assert employee_row.certification is not None
    assert employee_row.latest_final_exam is not None
    assert employee_row.latest_final_exam.correct_count == 14

    detail = await get_admin_employee_results(
        db_session,
        organization_id=organization_id,
        employee_profile_id=employee_profile_id,
    )
    assert detail.final_exam.certification is not None
    assert detail.final_exam.history[0].result_id == finished.result.id

    admin_result = await get_admin_final_exam_result(
        db_session,
        organization_id=organization_id,
        attempt_id=attempt_id,
    )
    assert admin_result.result.id == finished.result.id
    assert admin_result.result.pass_status == "passed"


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
async def test_final_exam_write_guards_preserve_answers_results_and_audit(
    db_session: AsyncSession, operation: str, state: str, error: str
) -> None:
    from app.models import SubmittedAnswer

    context = await _make_context(db_session)
    now = datetime.now(UTC)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    context.assignment.status = "completed"
    context.assignment.started_at = context.assignment.completed_at = now
    exam = make_assessment(context.training, None, assessment_type="menu_final_exam")
    db_session.add(exam)
    await db_session.flush()
    version = make_assessment_version(
        exam,
        context.training_version,
        None,
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
    )
    session = make_session(user, token_hash="b" * 64, csrf_token_hash="c" * 64)
    db_session.add_all([version, session])
    await db_session.flush()
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        version,
        question_count=20,
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
            await save_final_exam_answer(
                db_session,
                **args,
                attempt_question_id=question_id,
                answer_payload=SingleChoiceSubmission(mechanic="single_choice", option_id=uuid4()),
            )
        else:
            await finish_final_exam_attempt(db_session, **args)
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
async def test_final_exam_takeover_preserves_terminal_state_and_replays_once(
    db_session: AsyncSession,
    state: str,
) -> None:
    from app.models import AttemptDeviceLease
    from app.services.final_exam_attempts import takeover_final_exam_attempt

    context = await _make_context(db_session)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    now = datetime.now(UTC)
    exam = make_assessment(context.training, None, assessment_type="menu_final_exam")
    db_session.add(exam)
    await db_session.flush()
    version = make_assessment_version(
        exam,
        context.training_version,
        None,
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
    )
    session = make_session(user, token_hash="e" * 64, csrf_token_hash="f" * 64)
    db_session.add_all([version, session])
    await db_session.flush()
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        version,
        question_count=20,
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
        first = await takeover_final_exam_attempt(db_session, **args)
        assert first.lease_generation == 2 and not first.replayed
        before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
        replay = await takeover_final_exam_attempt(db_session, **args)
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
            await takeover_final_exam_attempt(db_session, **args)
        await db_session.rollback()
        assert (await db_session.get_one(AttemptDeviceLease, lease_id)).generation == 1
        assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
