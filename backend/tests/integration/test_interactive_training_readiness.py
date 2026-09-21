from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.final_exam_readiness import (
    ensure_final_exam_readiness,
    get_final_exam_readiness,
)
from app.services.question_review import (
    ensure_practice_readiness,
    get_interactive_training_readiness,
    get_practice_readiness,
)
from tests.factories.assessments import make_assessment_readiness
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.integration
@pytest.mark.parametrize("has_lesson_readiness", [False, True])
async def test_lesson_readiness_excludes_whole_menu_assessments(
    db_session: AsyncSession, has_lesson_readiness: bool
) -> None:
    context = await _make_context(db_session)
    scope = {
        "organization_id": context.training.organization_id,
        "location_id": context.training.location_id,
        "training_version_id": context.training_version.id,
    }
    if has_lesson_readiness:
        db_session.add(make_assessment_readiness(context.assessment_version))
        await db_session.flush()
    before = await get_interactive_training_readiness(db_session, **scope)

    now = datetime.now(UTC)
    await ensure_practice_readiness(db_session, **scope, actor_user_id=context.actor.id, now=now)
    await ensure_final_exam_readiness(db_session, **scope, actor_user_id=context.actor.id, now=now)
    practice = await get_practice_readiness(db_session, **scope)
    final_exam = await get_final_exam_readiness(db_session, **scope)
    assert practice.assessment_version_id is not None
    assert final_exam.assessment_version_id is not None
    assert practice.assessment_version_id != final_exam.assessment_version_id
    assert (practice.required_count, final_exam.required_count) == (10, 20)
    assert practice.status == final_exam.status == "blocked"

    after = await get_interactive_training_readiness(db_session, **scope)
    assert after == before
    assert after.training_version_id == context.training_version.id
    if has_lesson_readiness:
        assert len(after.lessons) == 1
        lesson = after.lessons[0]
        assert lesson.assessment_version_id == context.assessment_version.id
        assert lesson.lesson_id == context.lesson_version.lesson_id
        assert lesson.lesson_version_id == context.lesson_version.id
        assert lesson.eligible_count == lesson.required_count == 5
        assert lesson.can_start is True
    else:
        assert after.lessons == []


@pytest.mark.integration
@pytest.mark.parametrize("foreign_scope", ["organization_id", "location_id"])
async def test_lesson_readiness_hides_foreign_scope(
    db_session: AsyncSession, foreign_scope: str
) -> None:
    context = await _make_context(db_session)
    scope = {
        "organization_id": context.training.organization_id,
        "location_id": context.training.location_id,
        "training_version_id": context.training_version.id,
    }
    scope[foreign_scope] = uuid4()
    with pytest.raises(APIError) as caught:
        await get_interactive_training_readiness(db_session, **scope)
    assert caught.value.status_code == 404
    assert caught.value.code == "RESOURCE_NOT_FOUND"
