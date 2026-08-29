from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assessment,
    AssessmentVersion,
    EmployeeProfile,
    LessonVersion,
    Question,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionVersion,
    Training,
    TrainingAssignment,
    TrainingVersion,
    User,
)
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_question_pool,
    make_assessment_readiness,
    make_assessment_version,
    make_attempt_device_lease,
    make_attempt_option,
    make_attempt_question,
    make_attempt_result,
    make_question,
    make_question_candidate,
    make_question_generation_rule,
    make_question_option,
    make_question_version,
    make_submitted_answer,
)
from tests.factories.auth import make_session
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_user,
)
from tests.factories.training import (
    make_lesson,
    make_lesson_version,
    make_training,
    make_training_assignment,
    make_training_module,
    make_training_module_version,
    make_training_version,
)


@dataclass(frozen=True)
class AssessmentContext:
    actor: User
    employee: EmployeeProfile
    training: Training
    training_version: TrainingVersion
    lesson_version: LessonVersion
    assignment: TrainingAssignment
    rule: QuestionGenerationRule
    candidate: QuestionCandidate
    question: Question
    question_version: QuestionVersion
    assessment: Assessment
    assessment_version: AssessmentVersion


async def _make_context(session: AsyncSession) -> AssessmentContext:
    organization = make_organization()
    location = make_location(organization)
    actor = make_user(email_normalized="assessment-admin@example.com")
    employee_user = make_user(email_normalized="assessment-employee@example.com")
    session.add_all([organization, location, actor, employee_user])
    await session.flush()

    membership = make_membership(organization, employee_user)
    session.add(membership)
    await session.flush()
    employee = make_employee_profile(
        membership,
        organization.id,
        location_id=location.id,
    )
    training = make_training(organization.id, location.id)
    module = make_training_module(training)
    session.add_all([employee, training, module])
    await session.flush()

    now = datetime.now(UTC)
    training_version = make_training_version(
        training,
        actor.id,
        status="published",
        published_by_user_id=actor.id,
        published_at=now,
    )
    session.add(training_version)
    await session.flush()
    module_version = make_training_module_version(training_version, module)
    lesson = make_lesson(module)
    session.add_all([module_version, lesson])
    await session.flush()
    lesson_version = make_lesson_version(module_version, lesson)
    assignment = make_training_assignment(employee, training, training_version)
    rule = make_question_generation_rule()
    session.add_all([lesson_version, assignment, rule])
    await session.flush()

    candidate = make_question_candidate(rule, training_version, lesson_version)
    question = make_question(candidate)
    assessment = make_assessment(training, lesson_version)
    session.add_all([candidate, question, assessment])
    await session.flush()
    question_version = make_question_version(question, candidate, actor.id)
    assessment_version = make_assessment_version(
        assessment,
        training_version,
        lesson_version,
    )
    session.add_all([question_version, assessment_version])
    await session.flush()

    return AssessmentContext(
        actor=actor,
        employee=employee,
        training=training,
        training_version=training_version,
        lesson_version=lesson_version,
        assignment=assignment,
        rule=rule,
        candidate=candidate,
        question=question,
        question_version=question_version,
        assessment=assessment,
        assessment_version=assessment_version,
    )


async def _assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_complete_interactive_training_persistence_graph_persists(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
    option = make_question_option(context.question_version, 0)
    pool = make_assessment_question_pool(context.assessment_version, context.question_version)
    readiness = make_assessment_readiness(context.assessment_version)
    completed_at = datetime.now(UTC)
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        context.assessment_version,
        status="completed",
        completed_at=completed_at,
    )
    auth_session = make_session(context.actor)
    db_session.add_all([option, pool, readiness, attempt, auth_session])
    await db_session.flush()
    attempt_question = make_attempt_question(attempt, context.question_version)
    lease = make_attempt_device_lease(attempt, auth_session)
    db_session.add_all([attempt_question, lease])
    await db_session.flush()
    db_session.add_all(
        [
            make_attempt_option(attempt_question, option),
            make_submitted_answer(attempt, attempt_question),
            make_attempt_result(attempt),
        ]
    )

    await db_session.commit()

    assert readiness.status == "warning"
    assert attempt.status == "completed"
    assert attempt.completed_at == completed_at


@pytest.mark.integration
async def test_only_one_active_attempt_survives_database_enforcement(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
    db_session.add_all(
        [
            make_assessment_attempt(
                context.employee,
                context.assignment,
                context.assessment_version,
            ),
            make_assessment_attempt(
                context.employee,
                context.assignment,
                context.assessment_version,
            ),
        ]
    )

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_answer_is_unique_per_attempt_question(db_session: AsyncSession) -> None:
    context = await _make_context(db_session)
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        context.assessment_version,
    )
    db_session.add(attempt)
    await db_session.flush()
    attempt_question = make_attempt_question(attempt, context.question_version)
    db_session.add(attempt_question)
    await db_session.flush()
    db_session.add_all(
        [
            make_submitted_answer(attempt, attempt_question),
            make_submitted_answer(attempt, attempt_question),
        ]
    )

    await _assert_integrity_error(db_session)
