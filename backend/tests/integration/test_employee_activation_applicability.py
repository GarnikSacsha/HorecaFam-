from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.applicability import evaluate_activation_applicability


async def test_stage6_activation_applicability_is_explicitly_empty(
    db_session: AsyncSession,
) -> None:
    result = await evaluate_activation_applicability(
        db_session,
        organization_id=uuid4(),
        employee_profile_id=uuid4(),
    )

    assert result.published_content_count == 0
    assert result.assignment_count == 0
    assert result.notification_count == 0
