from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BackgroundJob, TrainingAssignment
from app.services.applicability import evaluate_activation_applicability
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)
from tests.factories.training import (
    make_training,
    make_training_version,
    make_training_version_audience,
)


async def test_applicability_creates_one_assignment_and_notification_without_duplicates(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    role = make_role(organization)
    user = make_user()
    published_at = datetime.now(UTC)
    membership = make_membership(
        organization,
        user,
        status="pending",
        activated_at=None,
    )
    db_session.add_all([organization, location, role, user, membership])
    await db_session.flush()
    employee = make_employee_profile(
        membership,
        organization.id,
        location_id=location.id,
        operational_role_id=role.id,
    )
    db_session.add(employee)
    await db_session.flush()
    training = make_training(organization.id, location.id)
    version = make_training_version(
        training,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=published_at,
    )
    db_session.add_all(
        [
            training,
            version,
            make_training_version_audience(version, role),
        ]
    )
    await db_session.commit()

    created = await evaluate_activation_applicability(
        db_session,
        organization_id=organization.id,
        employee_profile_id=employee.id,
        effective_membership_status="active",
    )
    membership.status = "active"
    membership.activated_at = published_at
    retained = await evaluate_activation_applicability(
        db_session,
        organization_id=organization.id,
        employee_profile_id=employee.id,
    )
    await db_session.commit()

    assert created.assignment_count == 1
    assert created.notification_count == 1
    assert retained.assignment_count == 0
    assert retained.notification_count == 0
    assert await db_session.scalar(select(func.count()).select_from(TrainingAssignment)) == 1
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(BackgroundJob.job_type == "training_assignment_notification")
        )
        == 1
    )

    other_role = make_role(organization, code="runner")
    db_session.add(other_role)
    await db_session.flush()
    employee.operational_role_id = other_role.id
    revoked = await evaluate_activation_applicability(
        db_session,
        organization_id=organization.id,
        employee_profile_id=employee.id,
    )
    membership.status = "disabled"
    membership.disabled_at = datetime.now(UTC)
    disabled = await evaluate_activation_applicability(
        db_session,
        organization_id=organization.id,
        employee_profile_id=employee.id,
    )
    employee.operational_role_id = role.id
    reactivated = await evaluate_activation_applicability(
        db_session,
        organization_id=organization.id,
        employee_profile_id=employee.id,
        effective_membership_status="active",
    )
    await db_session.commit()

    assert revoked.revoked_assignment_count == 1
    assert revoked.effects == ("revoked",)
    assert disabled.effects == ("not_applicable",)
    assert reactivated.effects == ("created",)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(TrainingAssignment)
            .where(TrainingAssignment.status != "revoked")
        )
        == 1
    )
