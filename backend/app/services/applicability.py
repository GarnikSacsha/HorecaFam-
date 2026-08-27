from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ActivationApplicabilityResult:
    published_content_count: int
    assignment_count: int
    notification_count: int


async def evaluate_activation_applicability(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID,
) -> ActivationApplicabilityResult:
    """Фіксує нульову Stage 6 межу до появи навчального контенту."""
    _ = db, organization_id, employee_profile_id
    return ActivationApplicabilityResult(
        published_content_count=0,
        assignment_count=0,
        notification_count=0,
    )
