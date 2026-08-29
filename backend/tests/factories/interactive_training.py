from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssessmentAttempt, OrganizationMembership, Session, User
from app.schemas.assessment import InteractiveAttemptStartResponse
from app.services.interactive_attempts import start_or_resume_interactive_attempt
from tests.factories.assessments import (
    make_assessment_question_pool,
    make_assessment_readiness,
    make_question,
    make_question_option,
    make_question_version,
)
from tests.factories.auth import make_session
from tests.factories.training import make_lesson_completion
from tests.integration.test_assessment_persistence import AssessmentContext, _make_context


@dataclass(frozen=True, slots=True)
class InteractiveRuntimeContext:
    persistence: AssessmentContext
    employee_user: User
    session: Session
    attempt: AssessmentAttempt
    start: InteractiveAttemptStartResponse


async def arrange_interactive_runtime(
    db: AsyncSession,
    *,
    token_prefix: str = "5",
) -> InteractiveRuntimeContext:
    context = await _make_context(db)
    membership = await db.get(OrganizationMembership, context.employee.membership_id)
    if membership is None:
        raise RuntimeError("Employee membership is unavailable")
    employee_user = await db.get(User, membership.user_id)
    if employee_user is None:
        raise RuntimeError("Employee user is unavailable")
    now = datetime.now(UTC)
    auth_session = make_session(
        employee_user,
        token_hash=token_prefix * 64,
        csrf_token_hash=str((int(token_prefix) + 1) % 10) * 64,
    )
    db.add_all(
        [
            auth_session,
            make_lesson_completion(
                context.assignment,
                context.lesson_version,
                employee_user.id,
                completed_at=now,
            ),
        ]
    )
    await db.flush()

    versions = [context.question_version]
    for index in range(1, 5):
        question = make_question(context.candidate)
        db.add(question)
        await db.flush()
        version = make_question_version(
            question,
            context.candidate,
            context.actor.id,
            prompt_payload={"text": f"Question {index}"},
            source_fingerprint=f"{index}" * 64,
        )
        db.add(version)
        await db.flush()
        versions.append(version)
    for index, version in enumerate(versions):
        db.add(
            make_assessment_question_pool(
                context.assessment_version,
                version,
                coverage_key=f"menu-item-{index}",
            )
        )
        db.add_all([make_question_option(version, 0), make_question_option(version, 1)])
    db.add(
        make_assessment_readiness(
            context.assessment_version,
            status="warning",
            eligible_count=5,
        )
    )
    await db.flush()
    start = await start_or_resume_interactive_attempt(
        db,
        organization_id=context.assignment.organization_id,
        location_id=context.assignment.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=auth_session.id,
        lesson_id=context.lesson_version.lesson_id,
        presentation_locale="uk",
        idempotency_key=f"runtime-start-{token_prefix}",
        request_id=auth_session.id,
        now=now,
    )
    attempt = await db.get(AssessmentAttempt, start.attempt.id)
    if attempt is None:
        raise RuntimeError("Started Attempt is unavailable")
    return InteractiveRuntimeContext(
        persistence=context,
        employee_user=employee_user,
        session=auth_session,
        attempt=attempt,
        start=start,
    )
