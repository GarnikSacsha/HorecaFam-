from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, EmployeeProfile, User
from tests.factories import (
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)


async def assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_normalized_email_is_globally_unique(db_session: AsyncSession) -> None:
    db_session.add(make_user(email_normalized="  Employee@Example.COM "))
    await db_session.commit()

    db_session.add(make_user(email_normalized="employee@example.com"))
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_database_rejects_noncanonical_stored_email(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(User).values(
                email_normalized=" Employee@Example.COM ",
                preferred_locale="uk",
            )
        )
    await db_session.rollback()


@pytest.mark.integration
async def test_membership_relationships_and_unique_ownership(db_session: AsyncSession) -> None:
    organization = make_organization()
    location = make_location(organization)
    role = make_role(organization)
    user = make_user()
    membership = make_membership(organization, user)
    db_session.add_all([organization, location, role, user, membership])
    await db_session.commit()

    assert membership.organization is organization
    assert membership.user is user
    assert location in organization.locations
    assert role in organization.operational_roles
    assert membership in organization.memberships
    assert membership in user.memberships

    db_session.add(make_membership(organization, user))
    await assert_integrity_error(db_session)


@pytest.mark.integration
@pytest.mark.parametrize("status", ["paused", "deleted", "invited"])
async def test_membership_rejects_noncanonical_states(
    db_session: AsyncSession,
    status: str,
) -> None:
    organization = make_organization()
    user = make_user()
    membership = make_membership(organization, user, status=status)
    db_session.add_all([organization, user, membership])

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_training_participation_accepts_pause_and_rejects_unknown_state(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    paused_user = make_user(email_normalized="paused-participation@example.com")
    paused = make_membership(
        organization,
        paused_user,
        training_participation_status="paused",
    )
    db_session.add_all([organization, paused_user, paused])
    await db_session.commit()
    assert paused.status == "active"
    assert paused.training_participation_status == "paused"

    invalid_user = make_user(email_normalized="invalid-participation@example.com")
    invalid = make_membership(
        organization,
        invalid_user,
        training_participation_status="stopped",
    )
    db_session.add_all([invalid_user, invalid])
    await assert_integrity_error(db_session)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "activated_at", "disabled_at"),
    [
        ("active", None, None),
        ("disabled", datetime.now(UTC), None),
        ("pending", datetime.now(UTC), None),
    ],
)
async def test_membership_status_requires_matching_timestamps(
    db_session: AsyncSession,
    status: str,
    activated_at: datetime | None,
    disabled_at: datetime | None,
) -> None:
    organization = make_organization()
    user = make_user()
    db_session.add_all(
        [
            organization,
            make_membership(
                organization,
                user,
                status=status,
                activated_at=activated_at,
                disabled_at=disabled_at,
            ),
        ]
    )

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_only_one_active_role_code_exists_per_organization(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    db_session.add_all(
        [
            organization,
            make_role(organization, code="waiter", status="active"),
            make_role(organization, code="waiter", status="archived"),
        ]
    )
    await db_session.commit()

    db_session.add(make_role(organization, code="waiter", status="active"))
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_referenced_organization_cannot_be_deleted(db_session: AsyncSession) -> None:
    organization = make_organization()
    db_session.add_all([organization, make_location(organization)])
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            delete(type(organization)).where(type(organization).id == organization.id)
        )
    await db_session.rollback()


@pytest.mark.integration
async def test_employee_profile_allows_incomplete_placeholder(db_session: AsyncSession) -> None:
    organization = make_organization()
    user = make_user()
    membership = make_membership(organization, user)
    profile = EmployeeProfile(membership=membership, organization_id=organization.id)
    db_session.add_all([organization, user, membership, profile])
    await db_session.commit()

    assert profile.membership is membership
    assert profile.first_name is None
    assert profile.last_name is None
    assert profile.operational_role_id is None
    assert profile.location_id is None


@pytest.mark.integration
async def test_employee_profile_is_unique_per_membership(db_session: AsyncSession) -> None:
    organization = make_organization()
    user = make_user()
    membership = make_membership(organization, user)
    db_session.add_all(
        [
            organization,
            user,
            membership,
            EmployeeProfile(membership=membership, organization_id=organization.id),
            EmployeeProfile(membership=membership, organization_id=organization.id),
        ]
    )

    await assert_integrity_error(db_session)


@pytest.mark.integration
@pytest.mark.parametrize("foreign_reference", ["role", "location"])
async def test_employee_profile_rejects_cross_organization_references(
    db_session: AsyncSession,
    foreign_reference: str,
) -> None:
    organization_a = make_organization(name="Organization A")
    organization_b = make_organization(name="Organization B")
    user = make_user()
    membership = make_membership(organization_a, user)
    role_b = make_role(organization_b)
    location_b = make_location(organization_b)
    db_session.add_all([organization_a, organization_b, user, membership, role_b, location_b])
    await db_session.flush()

    profile = EmployeeProfile(
        membership=membership,
        organization_id=organization_a.id,
        operational_role_id=role_b.id if foreign_reference == "role" else None,
        location_id=location_b.id if foreign_reference == "location" else None,
    )
    db_session.add(profile)

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_audit_event_persists_controlled_actor_and_database_timestamp(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    user = make_user()
    event = AuditEvent(
        organization=organization,
        actor_user=user,
        actor_type="user",
        action="membership.created",
        target_type="organization_membership",
        outcome="success",
        new_values={"status": "pending"},
    )
    db_session.add_all([organization, user, event])
    await db_session.commit()
    await db_session.refresh(event)

    assert event.created_at is not None
    assert event.created_at.tzinfo is not None


@pytest.mark.integration
async def test_audit_event_rejects_user_actor_without_user(db_session: AsyncSession) -> None:
    event = AuditEvent(
        actor_type="user",
        action="membership.created",
        target_type="organization_membership",
        outcome="success",
    )
    db_session.add(event)

    await assert_integrity_error(db_session)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("actor_type", "outcome"),
    [("employee", "success"), ("system", "unknown")],
)
async def test_audit_event_rejects_noncanonical_values(
    db_session: AsyncSession,
    actor_type: str,
    outcome: str,
) -> None:
    event = AuditEvent(
        actor_type=actor_type,
        action="membership.created",
        target_type="organization_membership",
        outcome=outcome,
    )
    db_session.add(event)

    await assert_integrity_error(db_session)
