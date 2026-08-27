from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiIdempotencyRecord, AuditEvent, EmployeeProfile, OrganizationMembership
from app.schemas.employees import EmployeeUpdate
from app.services.employees import activate_employee, update_pending_employee_profile
from tests.factories.identity import (
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)


async def test_profile_update_rolls_back_domain_and_audit_when_commit_fails(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization = make_organization(name="Rollback organization")
    admin = make_user(email_normalized="rollback-admin@example.com")
    employee = make_user(email_normalized="rollback-employee@example.com")
    membership = make_membership(
        organization,
        employee,
        status="pending",
        activated_at=None,
    )
    db_session.add_all([organization, admin, employee, membership])
    await db_session.flush()
    profile = EmployeeProfile(
        membership_id=membership.id,
        organization_id=organization.id,
        first_name="Original",
    )
    db_session.add(profile)
    await db_session.commit()
    organization_id = organization.id
    profile_id = profile.id
    admin_id = admin.id
    original_commit = db_session.commit

    async def fail_commit() -> None:
        raise RuntimeError("forced test-only commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced test-only commit failure"):
        await update_pending_employee_profile(
            db_session,
            organization_id=organization_id,
            employee_id=profile_id,
            actor_user_id=admin_id,
            payload=EmployeeUpdate(first_name="Changed"),
            request_id=uuid4(),
        )
    monkeypatch.setattr(db_session, "commit", original_commit)

    db_session.expire_all()
    assert (await db_session.get_one(EmployeeProfile, profile_id)).first_name == "Original"
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_activation_rolls_back_domain_and_audit_when_commit_fails(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization = make_organization(name="Activation rollback organization")
    admin = make_user(email_normalized="activation-rollback-admin@example.com")
    employee = make_user(email_normalized="activation-rollback-employee@example.com")
    membership = make_membership(
        organization,
        employee,
        status="pending",
        activated_at=None,
    )
    role = make_role(organization)
    location = make_location(organization)
    db_session.add_all([organization, admin, employee, membership, role, location])
    await db_session.flush()
    profile = EmployeeProfile(
        membership_id=membership.id,
        organization_id=organization.id,
        first_name="Iryna",
        last_name="Koval",
        operational_role_id=role.id,
        location_id=location.id,
    )
    db_session.add(profile)
    await db_session.commit()
    organization_id = organization.id
    membership_id = membership.id
    profile_id = profile.id
    admin_id = admin.id
    original_commit = db_session.commit

    async def fail_commit() -> None:
        raise RuntimeError("forced test-only activation commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced test-only activation commit failure"):
        await activate_employee(
            db_session,
            organization_id=organization_id,
            employee_id=profile_id,
            actor_user_id=admin_id,
            idempotency_key="rollback-activation",
            now=profile.created_at,
            request_id=uuid4(),
        )
    monkeypatch.setattr(db_session, "commit", original_commit)

    db_session.expire_all()
    stored = await db_session.get_one(OrganizationMembership, membership_id)
    assert stored.status == "pending"
    assert stored.activated_at is None
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ApiIdempotencyRecord)) == 0
