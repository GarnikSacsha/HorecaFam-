from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AttemptDeviceLease, AuditEvent, SubmittedAnswer
from app.schemas.assessment import SingleChoiceSubmission
from app.services.interactive_answers import submit_interactive_answer
from app.services.interactive_attempts import get_interactive_attempt, takeover_interactive_attempt
from tests.factories.assessments import make_assessment, make_assessment_version
from tests.factories.interactive_training import arrange_interactive_runtime


@pytest.mark.integration
@pytest.mark.parametrize(
    "family,count", [("whole_menu_knowledge_check", 10), ("menu_final_exam", 20)]
)
@pytest.mark.parametrize("operation", ["answer", "read", "takeover", "replay"])
async def test_interactive_boundary_rejects_other_assessment_families(
    db_session: AsyncSession, family: str, count: int, operation: str
) -> None:
    context = await arrange_interactive_runtime(db_session)
    attempt = context.attempt
    question = context.start.attempt.questions[0]
    scope: dict[str, Any] = dict(
        organization_id=attempt.organization_id,
        location_id=attempt.location_id,
        employee_profile_id=attempt.employee_profile_id,
        attempt_id=attempt.id,
        session_id=context.session.id,
    )
    answer: dict[str, Any] = dict(
        actor_user_id=context.employee_user.id,
        attempt_question_id=question.id,
        answer_payload=SingleChoiceSubmission(
            mechanic="single_choice", option_id=question.options[0].id
        ),
        lease_generation=1,
        idempotency_key="family-answer",
        request_id=context.session.id,
        now=datetime.now(UTC),
    )
    if operation == "replay":
        await submit_interactive_answer(db_session, **scope, **answer)
    assessment = make_assessment(context.persistence.training, None, assessment_type=family)
    db_session.add(assessment)
    await db_session.flush()
    version = make_assessment_version(
        assessment,
        context.persistence.training_version,
        None,
        question_count=count,
        feedback_policy="after_final_submission",
    )
    db_session.add(version)
    await db_session.flush()
    attempt.assessment_version_id = version.id
    attempt.question_count = count
    await db_session.commit()
    before = [
        await db_session.scalar(select(func.count()).select_from(m))
        for m in (SubmittedAnswer, AuditEvent)
    ]
    lease = await db_session.scalar(
        select(AttemptDeviceLease).where(AttemptDeviceLease.attempt_id == attempt.id)
    )
    assert lease is not None
    generation = lease.generation
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        if operation in {"answer", "replay"}:
            await submit_interactive_answer(db_session, **scope, **answer)
        elif operation == "read":
            await get_interactive_attempt(db_session, **scope)
        else:
            await takeover_interactive_attempt(
                db_session,
                **scope,
                actor_user_id=context.employee_user.id,
                idempotency_key="family-takeover",
                request_id=context.session.id,
                now=datetime.now(UTC),
            )
    assert [
        await db_session.scalar(select(func.count()).select_from(m))
        for m in (SubmittedAnswer, AuditEvent)
    ] == before
    await db_session.refresh(lease)
    assert lease.generation == generation
