import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import APIError
from app.models import (
    AssessmentAttempt,
    AssessmentQuestionPool,
    AttemptQuestion,
    LessonQuestionCycle,
    LessonQuestionCycleItem,
    Question,
    QuestionVersion,
)
from app.schemas.assessment import (
    InteractiveAttemptStartResponse,
    LessonQuestionCycleResponse,
    SingleChoiceSubmission,
)
from app.services.interactive_answers import submit_interactive_answer
from app.services.interactive_attempts import start_or_resume_interactive_attempt
from app.services.interactive_cycles import cycle_summary, restart_lesson_cycle
from tests.factories.assessments import (
    make_assessment_question_pool,
    make_assessment_readiness,
    make_assessment_version,
    make_question,
    make_question_option,
    make_question_version,
)
from tests.factories.interactive_training import (
    InteractiveRuntimeContext,
    arrange_interactive_runtime,
)


@pytest.mark.integration
async def test_foreign_cycle_is_hidden_and_cross_tenant_reservation_is_rejected(
    db_session: AsyncSession,
) -> None:
    from sqlalchemy.exc import IntegrityError

    first = await arrange_interactive_runtime(db_session, token_prefix="7")
    first.persistence.actor.email_normalized = f"first-admin-{uuid4()}@example.com"
    first.employee_user.email_normalized = f"first-employee-{uuid4()}@example.com"
    first.persistence.rule.code = "cycle.first_tenant"
    await db_session.commit()
    second = await arrange_interactive_runtime(db_session, token_prefix="8")
    foreign_cycle = await db_session.scalar(
        select(LessonQuestionCycle).where(
            LessonQuestionCycle.employee_profile_id == second.persistence.employee.id
        )
    )
    own_cycle = await db_session.scalar(
        select(LessonQuestionCycle).where(
            LessonQuestionCycle.employee_profile_id == first.persistence.employee.id
        )
    )
    assert foreign_cycle is not None and own_cycle is not None
    item = await db_session.scalar(
        select(LessonQuestionCycleItem).where(LessonQuestionCycleItem.cycle_id == own_cycle.id)
    )
    assert item is not None
    context = first.persistence
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await restart_lesson_cycle(
            db_session,
            organization_id=context.assignment.organization_id,
            location_id=context.assignment.location_id,
            employee_profile_id=context.employee.id,
            actor_user_id=first.employee_user.id,
            lesson_id=context.lesson_version.lesson_id,
            expected_cycle_id=foreign_cycle.id,
            idempotency_key="foreign-cycle",
            request_id=uuid4(),
            now=datetime.now(UTC),
        )
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                LessonQuestionCycleItem(
                    cycle_id=foreign_cycle.id,
                    question_id=item.question_id,
                    question_version_id=item.question_version_id,
                    attempt_question_id=item.attempt_question_id,
                    origin="reserved",
                )
            )
            await db_session.flush()


async def start_again(
    db: AsyncSession, runtime: InteractiveRuntimeContext, key: str
) -> InteractiveAttemptStartResponse:
    context = runtime.persistence
    return await start_or_resume_interactive_attempt(
        db,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=runtime.employee_user.id,
        session_id=runtime.session.id,
        lesson_id=context.lesson_version.lesson_id,
        presentation_locale="uk",
        idempotency_key=key,
        request_id=uuid4(),
        now=datetime.now(UTC),
    )


@pytest.mark.integration
async def test_concurrent_restart_and_start_have_one_winner(db_session: AsyncSession) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    await finish(db_session, runtime)
    context = runtime.persistence
    cycle = await db_session.scalar(select(LessonQuestionCycle))
    assert cycle is not None
    expected_id = cycle.id
    await db_session.commit()
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def restart() -> LessonQuestionCycleResponse:
        async with factory() as db:
            return await restart_lesson_cycle(
                db,
                organization_id=context.assignment.organization_id,
                location_id=context.assignment.location_id,
                employee_profile_id=context.employee.id,
                actor_user_id=runtime.employee_user.id,
                lesson_id=context.lesson_version.lesson_id,
                expected_cycle_id=expected_id,
                idempotency_key="concurrent-restart",
                request_id=uuid4(),
                now=datetime.now(UTC),
            )

    restarted = await asyncio.wait_for(asyncio.gather(restart(), restart(), restart()), 20)
    assert len({r.id for r in restarted}) == 1

    async def start(key: str) -> InteractiveAttemptStartResponse:
        async with factory() as db:
            return await start_again(db, runtime, key)

    results = await asyncio.wait_for(asyncio.gather(*(start(str(i)) for i in range(3))), 20)
    assert len({r.attempt.id for r in results}) == 1
    assert sum(r.created for r in results) == 1
    assert len(list(await db_session.scalars(select(LessonQuestionCycleItem)))) == 10


@pytest.mark.integration
async def test_edited_question_version_does_not_become_unseen(db_session: AsyncSession) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    await finish(db_session, runtime)
    context = runtime.persistence
    question = await db_session.get_one(Question, context.question_version.question_id)
    revised = make_question_version(question, context.candidate, context.actor.id, version_number=2)
    db_session.add(revised)
    await db_session.flush()
    db_session.add(
        make_assessment_question_pool(context.assessment_version, revised, coverage_key="revised")
    )
    await db_session.commit()
    with pytest.raises(APIError, match="INTERACTIVE_CYCLE_EXHAUSTED"):
        await start_again(db_session, runtime, "revised-version")


@pytest.mark.integration
async def test_new_question_extends_cycle_as_one_question_attempt(db_session: AsyncSession) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    await finish(db_session, runtime)
    context = runtime.persistence
    question = make_question(context.candidate)
    db_session.add(question)
    await db_session.flush()
    version = make_question_version(question, context.candidate, context.actor.id)
    db_session.add(version)
    await db_session.flush()
    db_session.add(
        make_assessment_question_pool(context.assessment_version, version, coverage_key="new")
    )
    db_session.add_all([make_question_option(version, 0), make_question_option(version, 1)])
    await db_session.commit()
    started = await start_again(db_session, runtime, "new-question")
    assert len(started.attempt.questions) == 1
    assert len(list(await db_session.scalars(select(LessonQuestionCycle)))) == 1


@pytest.mark.integration
async def test_cycle_database_rejects_duplicate_reservation(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    await arrange_interactive_runtime(db_session)
    item = await db_session.scalar(select(LessonQuestionCycleItem))
    assert item is not None
    duplicate = LessonQuestionCycleItem(
        cycle_id=item.cycle_id,
        question_id=item.question_id,
        question_version_id=item.question_version_id,
        attempt_question_id=item.attempt_question_id,
        origin="reserved",
    )
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(duplicate)
            await db_session.flush()


@pytest.mark.integration
async def test_legacy_completed_history_bootstraps_without_repetition(
    db_session: AsyncSession,
) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    await finish(db_session, runtime)
    context = runtime.persistence
    await db_session.execute(delete(LessonQuestionCycleItem))
    await db_session.execute(delete(LessonQuestionCycle))
    await db_session.commit()
    summary = await cycle_summary(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_id=context.employee.id,
        lesson_id=context.lesson_version.lesson_id,
        assessment_version_id=context.assessment_version.id,
    )
    assert summary.id is None
    assert summary.answered_count == 5
    assert summary.remaining_count == 0
    assert summary.can_restart
    assert list(await db_session.scalars(select(LessonQuestionCycle))) == []
    with pytest.raises(APIError, match="INTERACTIVE_CYCLE_EXHAUSTED"):
        await start_again(db_session, runtime, "legacy")


@pytest.mark.integration
async def test_partial_snapshot_failure_rolls_back_reservation(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import interactive_attempts

    runtime = await arrange_interactive_runtime(db_session)
    await finish(db_session, runtime)
    context = runtime.persistence
    question = make_question(context.candidate)
    db_session.add(question)
    await db_session.flush()
    version = make_question_version(question, context.candidate, context.actor.id)
    db_session.add(version)
    await db_session.flush()
    db_session.add(
        make_assessment_question_pool(context.assessment_version, version, coverage_key="new")
    )
    db_session.add_all([make_question_option(version, 0), make_question_option(version, 1)])
    await db_session.commit()
    original = interactive_attempts._snapshot_question

    async def fail_after_snapshot(
        db: AsyncSession,
        *,
        attempt: AssessmentAttempt,
        pool: AssessmentQuestionPool,
        question_version: QuestionVersion,
        position: int,
    ) -> None:
        await original(
            db, attempt=attempt, pool=pool, question_version=question_version, position=position
        )
        raise RuntimeError("synthetic snapshot failure")

    monkeypatch.setattr(interactive_attempts, "_snapshot_question", fail_after_snapshot)
    with pytest.raises(RuntimeError, match="synthetic snapshot failure"):
        await start_again(db_session, runtime, "rollback")
    await db_session.rollback()
    assert len(list(await db_session.scalars(select(LessonQuestionCycleItem)))) == 5
    assert len(list(await db_session.scalars(select(AttemptQuestion)))) == 5


@pytest.mark.integration
async def test_database_rejects_interactive_count_ten(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    runtime = await arrange_interactive_runtime(db_session)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            runtime.attempt.question_count = 10
            await db_session.flush()


@pytest.mark.integration
async def test_latest_assessment_adds_only_new_stable_questions(db_session: AsyncSession) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    await finish(db_session, runtime)
    context = runtime.persistence
    newer = make_assessment_version(
        context.assessment, context.training_version, context.lesson_version, version_number=2
    )
    db_session.add(newer)
    await db_session.flush()
    for version in await db_session.scalars(select(QuestionVersion)):
        db_session.add(make_assessment_question_pool(newer, version, coverage_key=str(version.id)))
    question = make_question(context.candidate)
    db_session.add(question)
    await db_session.flush()
    version = make_question_version(question, context.candidate, context.actor.id)
    db_session.add(version)
    await db_session.flush()
    db_session.add(make_assessment_question_pool(newer, version, coverage_key="new"))
    db_session.add_all([make_question_option(version, 0), make_question_option(version, 1)])
    db_session.add(make_assessment_readiness(newer, status="ready", eligible_count=6))
    await db_session.commit()
    started = await start_again(db_session, runtime, "new-version")
    assert started.attempt.assessment_version_id == newer.id
    assert len(started.attempt.questions) == 1


@pytest.mark.integration
async def test_legacy_expired_history_is_not_reported_as_all_answered(
    db_session: AsyncSession,
) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    context = runtime.persistence
    runtime.attempt.status = "expired"
    await db_session.execute(delete(LessonQuestionCycleItem))
    await db_session.execute(delete(LessonQuestionCycle))
    await db_session.commit()
    state = await cycle_summary(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_id=context.employee.id,
        lesson_id=context.lesson_version.lesson_id,
        assessment_version_id=context.assessment_version.id,
    )
    assert state.status == "restart_required"
    assert state.answered_count == 0
    assert state.can_restart


async def finish(db: AsyncSession, runtime: InteractiveRuntimeContext) -> None:
    context = runtime.persistence
    for question in runtime.start.attempt.questions:
        await submit_interactive_answer(
            db,
            organization_id=context.assignment.organization_id,
            location_id=context.assignment.location_id,
            employee_profile_id=context.employee.id,
            actor_user_id=runtime.employee_user.id,
            session_id=runtime.session.id,
            attempt_id=runtime.attempt.id,
            attempt_question_id=question.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice", option_id=question.options[0].id
            ),
            lease_generation=1,
            idempotency_key=str(uuid4()),
            request_id=uuid4(),
            now=datetime.now(UTC),
        )


@pytest.mark.integration
async def test_restart_is_explicit_idempotent_and_preserves_results(
    db_session: AsyncSession,
) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    context = runtime.persistence
    scope = dict(
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_id=context.employee.id,
        lesson_id=context.lesson_version.lesson_id,
        assessment_version_id=context.assessment_version.id,
    )
    initial = await cycle_summary(
        db_session,
        organization_id=scope["organization_id"],
        location_id=scope["location_id"],
        employee_id=scope["employee_id"],
        lesson_id=scope["lesson_id"],
        assessment_version_id=scope["assessment_version_id"],
    )
    assert initial.status == "in_progress"
    assert not initial.can_restart
    with pytest.raises(APIError, match="INTERACTIVE_CYCLE_IN_PROGRESS"):
        await restart_lesson_cycle(
            db_session,
            organization_id=scope["organization_id"],
            location_id=scope["location_id"],
            employee_profile_id=context.employee.id,
            actor_user_id=runtime.employee_user.id,
            lesson_id=scope["lesson_id"],
            expected_cycle_id=initial.id,
            idempotency_key="blocked",
            request_id=uuid4(),
            now=datetime.now(UTC),
        )
    await finish(db_session, runtime)
    state = await cycle_summary(
        db_session,
        organization_id=scope["organization_id"],
        location_id=scope["location_id"],
        employee_id=scope["employee_id"],
        lesson_id=scope["lesson_id"],
        assessment_version_id=scope["assessment_version_id"],
    )
    assert state.status == "exhausted"
    assert state.answered_count == 5
    for _ in range(2):
        restarted = await restart_lesson_cycle(
            db_session,
            organization_id=scope["organization_id"],
            location_id=scope["location_id"],
            employee_profile_id=context.employee.id,
            actor_user_id=runtime.employee_user.id,
            lesson_id=scope["lesson_id"],
            expected_cycle_id=state.id,
            idempotency_key="restart",
            request_id=uuid4(),
            now=datetime.now(UTC),
        )
        assert restarted.number == 2
        assert restarted.remaining_count == 5
        assert restarted.answered_count == 0
    from app.models import AttemptResult

    assert len(list(await db_session.scalars(select(AttemptResult)))) == 1


@pytest.mark.integration
async def test_expired_unanswered_cycle_requires_explicit_restart(db_session: AsyncSession) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    context = runtime.persistence
    now = datetime.now(UTC) + timedelta(days=8)
    state = await cycle_summary(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_id=context.employee.id,
        lesson_id=context.lesson_version.lesson_id,
        assessment_version_id=context.assessment_version.id,
        now=now,
    )
    assert state.status == "restart_required"
    assert state.answered_count == 0
    restarted = await restart_lesson_cycle(
        db_session,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=runtime.employee_user.id,
        lesson_id=context.lesson_version.lesson_id,
        expected_cycle_id=state.id,
        idempotency_key="expire-restart",
        request_id=uuid4(),
        now=now,
    )
    assert restarted.number == 2
    await db_session.refresh(runtime.attempt)
    assert runtime.attempt.status == "expired"


@pytest.mark.integration
@pytest.mark.parametrize("pool_size", [8, 30])
async def test_lesson_cycle_never_repeats_and_completes_short_remainder(
    db_session: AsyncSession, pool_size: int
) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    context = runtime.persistence
    for index in range(5, pool_size):
        bank_question = make_question(context.candidate)
        db_session.add(bank_question)
        await db_session.flush()
        version = make_question_version(bank_question, context.candidate, context.actor.id)
        db_session.add(version)
        await db_session.flush()
        db_session.add(
            make_assessment_question_pool(
                context.assessment_version, version, coverage_key=f"item-{index}"
            )
        )
        db_session.add_all([make_question_option(version, 0), make_question_option(version, 1)])
    await db_session.commit()
    start = runtime.start
    seen: set[UUID] = set()
    batch_sizes = []
    while len(seen) < pool_size:
        ids = set(
            await db_session.scalars(
                select(AttemptQuestion.question_version_id).where(
                    AttemptQuestion.attempt_id == start.attempt.id
                )
            )
        )
        assert not seen.intersection(ids)
        seen.update(ids)
        batch_sizes.append(len(ids))
        for question in start.attempt.questions:
            response = await submit_interactive_answer(
                db_session,
                organization_id=context.assignment.organization_id,
                location_id=context.assignment.location_id,
                employee_profile_id=context.employee.id,
                actor_user_id=runtime.employee_user.id,
                session_id=runtime.session.id,
                attempt_id=start.attempt.id,
                attempt_question_id=question.id,
                answer_payload=SingleChoiceSubmission(
                    mechanic="single_choice",
                    option_id=question.options[
                        1 if len(ids) == 3 and question.position == 2 else 0
                    ].id,
                ),
                lease_generation=1,
                idempotency_key=str(uuid4()),
                request_id=uuid4(),
                now=datetime.now(UTC),
            )
        assert response.attempt_status == "completed"
        assert response.result is not None
        assert response.result.total_count == len(ids)
        if len(ids) == 3:
            assert response.result.correct_count == 2
            assert response.result.score_basis_points == 6666
        if len(seen) < pool_size:
            start = await start_or_resume_interactive_attempt(
                db_session,
                organization_id=context.assignment.organization_id,
                location_id=context.assignment.location_id,
                employee_profile_id=context.employee.id,
                actor_user_id=runtime.employee_user.id,
                session_id=runtime.session.id,
                lesson_id=context.lesson_version.lesson_id,
                presentation_locale="uk",
                idempotency_key=str(uuid4()),
                request_id=uuid4(),
                now=datetime.now(UTC),
            )
    assert batch_sizes == ([5, 3] if pool_size == 8 else [5] * 6)
    with pytest.raises(APIError, match="INTERACTIVE_CYCLE_EXHAUSTED"):
        await start_or_resume_interactive_attempt(
            db_session,
            organization_id=context.assignment.organization_id,
            location_id=context.assignment.location_id,
            employee_profile_id=context.employee.id,
            actor_user_id=runtime.employee_user.id,
            session_id=runtime.session.id,
            lesson_id=context.lesson_version.lesson_id,
            presentation_locale="uk",
            idempotency_key=str(uuid4()),
            request_id=uuid4(),
            now=datetime.now(UTC),
        )
