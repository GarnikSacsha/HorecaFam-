from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BackgroundJob,
    EmployeeProfile,
    OrganizationMembership,
    Training,
    TrainingAssignment,
    TrainingVersion,
    TrainingVersionAudience,
    User,
)


@dataclass(frozen=True)
class ActivationApplicabilityResult:
    published_content_count: int
    assignment_count: int
    notification_count: int
    revoked_assignment_count: int = 0
    effects: tuple[str, ...] = ()


async def _employee_context(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID,
) -> tuple[EmployeeProfile, OrganizationMembership, User] | None:
    return (
        (
            await db.execute(
                select(EmployeeProfile, OrganizationMembership, User)
                .join(
                    OrganizationMembership,
                    and_(
                        OrganizationMembership.id == EmployeeProfile.membership_id,
                        OrganizationMembership.organization_id == EmployeeProfile.organization_id,
                    ),
                )
                .join(User, User.id == OrganizationMembership.user_id)
                .where(
                    EmployeeProfile.id == employee_profile_id,
                    EmployeeProfile.organization_id == organization_id,
                )
                .with_for_update()
            )
        )
        .tuples()
        .one_or_none()
    )


async def _current_assignment(
    db: AsyncSession,
    *,
    employee_profile_id: UUID,
) -> TrainingAssignment | None:
    return cast(
        TrainingAssignment | None,
        await db.scalar(
            select(TrainingAssignment)
            .where(
                TrainingAssignment.employee_profile_id == employee_profile_id,
                TrainingAssignment.status != "revoked",
            )
            .with_for_update()
        ),
    )


async def _assignment_still_applies(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    profile: EmployeeProfile,
) -> bool:
    if (
        profile.location_id is None
        or profile.operational_role_id is None
        or assignment.location_id != profile.location_id
    ):
        return False
    audience_id = await db.scalar(
        select(TrainingVersionAudience.id).where(
            TrainingVersionAudience.training_version_id == assignment.training_version_id,
            TrainingVersionAudience.operational_role_id == profile.operational_role_id,
        )
    )
    return audience_id is not None


async def _published_target(
    db: AsyncSession,
    *,
    organization_id: UUID,
    profile: EmployeeProfile,
) -> tuple[Training, TrainingVersion] | None:
    if profile.location_id is None or profile.operational_role_id is None:
        return None
    return (
        (
            await db.execute(
                select(Training, TrainingVersion)
                .join(TrainingVersion, TrainingVersion.training_id == Training.id)
                .join(
                    TrainingVersionAudience,
                    TrainingVersionAudience.training_version_id == TrainingVersion.id,
                )
                .where(
                    Training.organization_id == organization_id,
                    Training.location_id == profile.location_id,
                    TrainingVersion.status == "published",
                    TrainingVersionAudience.operational_role_id == profile.operational_role_id,
                )
            )
        )
        .tuples()
        .one_or_none()
    )


async def evaluate_activation_applicability(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID,
    effective_membership_status: str | None = None,
    now: datetime | None = None,
) -> ActivationApplicabilityResult:
    """Застосовує одну межу призначення для всіх змін операційного профілю."""
    context = await _employee_context(
        db,
        organization_id=organization_id,
        employee_profile_id=employee_profile_id,
    )
    if context is None:
        return ActivationApplicabilityResult(0, 0, 0, effects=("not_applicable",))
    profile, membership, user = context
    membership_status = effective_membership_status or membership.status
    if membership_status != "active":
        return ActivationApplicabilityResult(0, 0, 0, effects=("not_applicable",))

    current = await _current_assignment(db, employee_profile_id=profile.id)
    effects: list[str] = []
    revoked_count = 0
    if current is not None and await _assignment_still_applies(
        db,
        assignment=current,
        profile=profile,
    ):
        return ActivationApplicabilityResult(1, 0, 0, effects=("retained",))
    if current is not None:
        changed_at = now or datetime.now(UTC)
        current.status = "revoked"
        current.revoked_at = changed_at
        current.revoke_reason = (
            "location_changed" if current.location_id != profile.location_id else "role_changed"
        )
        effects.append("revoked")
        revoked_count = 1
        await db.flush()

    target = await _published_target(
        db,
        organization_id=organization_id,
        profile=profile,
    )
    if target is None:
        if not effects:
            effects.append("not_applicable")
        return ActivationApplicabilityResult(
            0,
            0,
            0,
            revoked_assignment_count=revoked_count,
            effects=tuple(effects),
        )
    training, version = target
    assignment = TrainingAssignment(
        organization_id=organization_id,
        location_id=training.location_id,
        training_id=training.id,
        employee_profile_id=profile.id,
        training_version_id=version.id,
        status="assigned",
        source="automatic",
        assigned_at=now or datetime.now(UTC),
    )
    db.add(assignment)
    await db.flush()
    db.add(
        BackgroundJob(
            organization_id=organization_id,
            job_type="training_assignment_notification",
            status="pending",
            payload={
                "assignment_id": str(assignment.id),
                "template_code": "training_assigned",
                "locale": "en" if user.preferred_locale == "en" else "uk",
            },
            idempotency_key=f"assignment:{assignment.id}:created",
        )
    )
    effects.append("created")
    await db.flush()
    return ActivationApplicabilityResult(
        published_content_count=1,
        assignment_count=1,
        notification_count=1,
        revoked_assignment_count=revoked_count,
        effects=tuple(effects),
    )
