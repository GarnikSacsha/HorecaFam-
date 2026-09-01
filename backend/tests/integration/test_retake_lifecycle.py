import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.models import (
    AssessmentAttempt,
    AttemptResult,
    AttentionCase,
    AttentionCaseAction,
    AttentionCaseSource,
    RetakeRequirement,
    RetakeRequirementAction,
)
from app.services.retakes import (
    freeze_retake_clock,
    project_final_exam_follow_up,
    project_managed_requirement_completion,
    project_retake_deadlines,
    resume_retake_clock,
    retake_timing_state,
)
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
    make_attempt_result,
)
from tests.integration.test_assessment_persistence import _make_context


async def _project_in_independent_session(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    attempt_id: UUID,
    result_id: UUID,
) -> UUID:
    async with session_factory() as session:
        attempt = await session.get(AssessmentAttempt, attempt_id)
        result = await session.get(AttemptResult, result_id)
        assert attempt is not None
        assert result is not None
        requirement = await project_final_exam_follow_up(
            session,
            attempt=attempt,
            result=result,
        )
        assert requirement is not None
        requirement_id = requirement.id
        await session.commit()
        return requirement_id


async def _project_deadline_in_independent_session(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
) -> list[UUID]:
    async with session_factory() as session:
        cases = await project_retake_deadlines(session, now=now)
        case_ids = [case.id for case in cases]
        await session.commit()
        return case_ids


@pytest.mark.integration
async def test_failed_cycle_keeps_original_deadline_and_completes_on_later_pass(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
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

    failed_at = datetime.now(UTC).replace(microsecond=0)
    first_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        status="completed",
        question_count=20,
        completed_at=failed_at,
    )
    db_session.add(first_attempt)
    await db_session.flush()
    first_result = make_attempt_result(
        first_attempt,
        total_count=20,
        correct_count=13,
        score_basis_points=6500,
        pass_status="failed",
        completed_at=failed_at,
    )
    db_session.add(first_result)
    await db_session.flush()

    requirement = await project_final_exam_follow_up(
        db_session,
        attempt=first_attempt,
        result=first_result,
    )
    assert requirement is not None
    assert requirement.state == "active"
    assert requirement.confirmed_at == failed_at
    assert requirement.due_at == failed_at + timedelta(days=7)
    original_requirement_id = requirement.id
    original_due_at = requirement.due_at

    repeated_at = failed_at + timedelta(days=2)
    repeated_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        status="completed",
        question_count=20,
        completed_at=repeated_at,
    )
    db_session.add(repeated_attempt)
    await db_session.flush()
    repeated_result = make_attempt_result(
        repeated_attempt,
        total_count=20,
        correct_count=12,
        score_basis_points=6000,
        pass_status="failed",
        completed_at=repeated_at,
    )
    db_session.add(repeated_result)
    await db_session.flush()

    repeated_requirement = await project_final_exam_follow_up(
        db_session,
        attempt=repeated_attempt,
        result=repeated_result,
    )
    assert repeated_requirement is not None
    assert repeated_requirement.id == original_requirement_id
    assert repeated_requirement.due_at == original_due_at
    assert repeated_requirement.state == "active"

    assert await project_retake_deadlines(db_session, now=original_due_at) == [
        await db_session.scalar(
            select(AttentionCase).where(AttentionCase.case_type == "retake_overdue")
        )
    ]
    assert (
        await project_retake_deadlines(
            db_session,
            now=original_due_at + timedelta(minutes=1),
        )
        == []
    )
    overdue_case = await db_session.scalar(
        select(AttentionCase)
        .join(AttentionCaseSource)
        .where(AttentionCaseSource.retake_requirement_id == requirement.id)
    )
    assert overdue_case is not None
    assert overdue_case.state == "open"
    assert overdue_case.case_type == "retake_overdue"

    passed_at = failed_at + timedelta(days=8)
    passed_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        status="completed",
        question_count=20,
        completed_at=passed_at,
    )
    db_session.add(passed_attempt)
    await db_session.flush()
    passed_result = make_attempt_result(
        passed_attempt,
        total_count=20,
        correct_count=14,
        score_basis_points=7000,
        pass_status="passed",
        completed_at=passed_at,
    )
    db_session.add(passed_result)
    await db_session.flush()

    completed = await project_final_exam_follow_up(
        db_session,
        attempt=passed_attempt,
        result=passed_result,
    )
    assert completed is not None
    assert completed.id == original_requirement_id
    assert completed.state == "completed"
    assert completed.due_at == original_due_at
    assert completed.completed_at == passed_at
    assert completed.completion_attempt_id == passed_attempt.id
    assert overdue_case.state == "resolved"
    assert overdue_case.resolution_type == "requirement_completed"
    assert overdue_case.resolution_actor_type == "system"
    assert overdue_case.resolved_by_user_id is None
    assert overdue_case.resolved_at == passed_at

    await project_final_exam_follow_up(
        db_session,
        attempt=passed_attempt,
        result=passed_result,
    )
    await db_session.commit()

    requirement_count = await db_session.scalar(select(func.count()).select_from(RetakeRequirement))
    observed_count = await db_session.scalar(
        select(func.count())
        .select_from(RetakeRequirementAction)
        .where(RetakeRequirementAction.action == "attempt_observed")
    )
    completed_count = await db_session.scalar(
        select(func.count())
        .select_from(RetakeRequirementAction)
        .where(RetakeRequirementAction.action == "completed")
    )
    overdue_case_count = await db_session.scalar(
        select(func.count())
        .select_from(AttentionCase)
        .where(AttentionCase.case_type == "retake_overdue")
    )
    overdue_source_count = await db_session.scalar(
        select(func.count())
        .select_from(AttentionCaseSource)
        .where(AttentionCaseSource.retake_requirement_id == requirement.id)
    )
    overdue_resolution_count = await db_session.scalar(
        select(func.count())
        .select_from(AttentionCaseAction)
        .where(
            AttentionCaseAction.attention_case_id == overdue_case.id,
            AttentionCaseAction.action == "resolved",
        )
    )
    assert requirement_count == 1
    assert observed_count == 3
    assert completed_count == 1
    assert overdue_case_count == 1
    assert overdue_source_count == 1
    assert overdue_resolution_count == 1
    assert first_result.pass_status == "failed"
    assert repeated_result.pass_status == "failed"
    assert passed_result.pass_status == "passed"


@pytest.mark.integration
async def test_retake_timing_and_freeze_resume_preserve_exact_remaining_time(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
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
    failed_at = datetime.now(UTC).replace(microsecond=0)
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        status="completed",
        question_count=20,
        completed_at=failed_at,
    )
    db_session.add(attempt)
    await db_session.flush()
    result = make_attempt_result(
        attempt,
        total_count=20,
        correct_count=10,
        score_basis_points=5000,
        pass_status="failed",
        completed_at=failed_at,
    )
    db_session.add(result)
    await db_session.flush()
    requirement = await project_final_exam_follow_up(
        db_session,
        attempt=attempt,
        result=result,
    )
    assert requirement is not None

    assert retake_timing_state(requirement, failed_at + timedelta(hours=119)) == "scheduled"
    assert retake_timing_state(requirement, failed_at + timedelta(hours=120)) == "approaching"
    assert retake_timing_state(requirement, requirement.due_at) == "overdue"

    frozen_at = failed_at + timedelta(days=6)
    assert await freeze_retake_clock(db_session, requirement=requirement, now=frozen_at)
    assert not await freeze_retake_clock(
        db_session,
        requirement=requirement,
        now=frozen_at + timedelta(hours=1),
    )
    assert retake_timing_state(requirement, failed_at + timedelta(days=20)) == "frozen"

    resumed_at = frozen_at + timedelta(hours=9)
    assert await resume_retake_clock(db_session, requirement=requirement, now=resumed_at)
    assert not await resume_retake_clock(
        db_session,
        requirement=requirement,
        now=resumed_at + timedelta(hours=1),
    )
    assert requirement.frozen_seconds == 9 * 60 * 60
    assert requirement.due_at == failed_at + timedelta(days=7, hours=9)
    assert retake_timing_state(requirement, requirement.due_at) == "overdue"


@pytest.mark.integration
async def test_matching_admin_requirement_completes_with_one_immutable_attempt(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
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
    confirmed_at = datetime.now(UTC).replace(microsecond=0)
    requirement = RetakeRequirement(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        training_id=context.training.id,
        employee_profile_id=context.employee.id,
        assignment_id=context.assignment.id,
        target_assessment_id=final_exam.id,
        reason="management_follow_up",
        state="active",
        management_source_key="manager-observation",
        target_policy={"assessment_type": "menu_final_exam", "minimum_result": "passed"},
        confirmed_at=confirmed_at,
        confirmed_by_user_id=context.actor.id,
        due_at=confirmed_at + timedelta(days=7),
        revision=0,
    )
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        status="completed",
        question_count=20,
        completed_at=confirmed_at + timedelta(days=1),
    )
    db_session.add_all([requirement, attempt])
    await db_session.flush()
    result = make_attempt_result(
        attempt,
        total_count=20,
        correct_count=14,
        score_basis_points=7000,
        pass_status="passed",
        completed_at=attempt.completed_at,
    )
    db_session.add(result)
    await db_session.flush()

    completed = await project_managed_requirement_completion(
        db_session,
        attempt=attempt,
        result=result,
    )
    replay = await project_managed_requirement_completion(
        db_session,
        attempt=attempt,
        result=result,
    )

    assert completed == [requirement]
    assert replay == []
    assert requirement.state == "completed"
    assert requirement.completion_attempt_id == attempt.id
    assert requirement.completed_at == result.completed_at
    completed_actions = list(
        await db_session.scalars(
            select(RetakeRequirementAction).where(
                RetakeRequirementAction.retake_requirement_id == requirement.id,
                RetakeRequirementAction.action == "completed",
            )
        )
    )
    assert len(completed_actions) == 1


@pytest.mark.integration
async def test_concurrent_failed_results_keep_one_current_obligation(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    context = await _make_context(db_session)
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
    first_at = datetime.now(UTC).replace(microsecond=0)
    source_ids = []
    for completed_at in (first_at, first_at + timedelta(minutes=1)):
        attempt = make_assessment_attempt(
            context.employee,
            context.assignment,
            final_exam_version,
            status="completed",
            question_count=20,
            completed_at=completed_at,
        )
        db_session.add(attempt)
        await db_session.flush()
        result = make_attempt_result(
            attempt,
            total_count=20,
            correct_count=10,
            score_basis_points=5000,
            pass_status="failed",
            completed_at=completed_at,
        )
        db_session.add(result)
        await db_session.flush()
        source_ids.append((attempt.id, result.id))
    await db_session.commit()

    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        requirement_ids = await asyncio.gather(
            *[
                _project_in_independent_session(
                    session_factory,
                    attempt_id=attempt_id,
                    result_id=result_id,
                )
                for attempt_id, result_id in source_ids
            ]
        )
    finally:
        await engine.dispose()

    await db_session.rollback()
    assert len(set(requirement_ids)) == 1
    requirements = list(await db_session.scalars(select(RetakeRequirement)))
    actions = list(
        await db_session.scalars(
            select(RetakeRequirementAction).where(
                RetakeRequirementAction.action == "attempt_observed"
            )
        )
    )
    assert len(requirements) == 1
    assert requirements[0].due_at == first_at + timedelta(days=7)
    assert len(actions) == 2


@pytest.mark.integration
async def test_concurrent_deadline_projection_opens_one_overdue_case(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    context = await _make_context(db_session)
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
    failed_at = datetime.now(UTC).replace(microsecond=0)
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        final_exam_version,
        status="completed",
        question_count=20,
        completed_at=failed_at,
    )
    db_session.add(attempt)
    await db_session.flush()
    result = make_attempt_result(
        attempt,
        total_count=20,
        correct_count=10,
        score_basis_points=5000,
        pass_status="failed",
        completed_at=failed_at,
    )
    db_session.add(result)
    await db_session.flush()
    requirement = await project_final_exam_follow_up(
        db_session,
        attempt=attempt,
        result=result,
    )
    assert requirement is not None
    requirement_id = requirement.id
    due_at = requirement.due_at
    await db_session.commit()

    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        projected_ids = await asyncio.gather(
            _project_deadline_in_independent_session(session_factory, now=due_at),
            _project_deadline_in_independent_session(session_factory, now=due_at),
        )
    finally:
        await engine.dispose()

    await db_session.rollback()
    cases = list(
        await db_session.scalars(
            select(AttentionCase).where(AttentionCase.case_type == "retake_overdue")
        )
    )
    sources = list(
        await db_session.scalars(
            select(AttentionCaseSource).where(
                AttentionCaseSource.retake_requirement_id == requirement_id
            )
        )
    )
    opened_actions = list(
        await db_session.scalars(
            select(AttentionCaseAction).where(AttentionCaseAction.action == "opened")
        )
    )
    deadline_actions = list(
        await db_session.scalars(
            select(RetakeRequirementAction).where(
                RetakeRequirementAction.action == "deadline_projected"
            )
        )
    )
    assert sorted(len(ids) for ids in projected_ids) == [0, 1]
    assert len(cases) == 1
    assert len(sources) == 1
    assert sources[0].attention_case_id == cases[0].id
    assert len(opened_actions) == 1
    assert len(deadline_actions) == 1
