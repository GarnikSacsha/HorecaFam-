from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiIdempotencyRecord, AuditEvent, BackgroundJob, TrainingAssignment
from app.schemas.training import TrainingAssignmentCreate
from app.services.training_assignments import create_training_assignment
from tests.api.test_menu_admin_api import FIXED_NOW
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_user,
)
from tests.factories.training import make_training, make_training_version


async def test_assignment_create_rolls_back_domain_job_audit_and_idempotency_when_commit_fails(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization = make_organization(name="Assignment rollback organization")
    location = make_location(organization)
    admin = make_user(email_normalized="assignment-rollback-admin@example.com")
    employee_user = make_user(email_normalized="assignment-rollback-employee@example.com")
    membership = make_membership(organization, employee_user, activated_at=FIXED_NOW)
    db_session.add_all([organization, location, admin, employee_user, membership])
    await db_session.flush()
    employee = make_employee_profile(
        membership,
        organization.id,
        location_id=location.id,
    )
    training = make_training(organization.id, location.id)
    db_session.add_all([employee, training])
    await db_session.flush()
    version = make_training_version(
        training,
        admin.id,
        status="published",
        published_by_user_id=admin.id,
        published_at=FIXED_NOW,
    )
    db_session.add(version)
    await db_session.commit()
    organization_id = organization.id
    employee_id = employee.id
    admin_id = admin.id
    original_commit = db_session.commit

    async def fail_commit() -> None:
        raise RuntimeError("forced test-only assignment commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced test-only assignment commit failure"):
        await create_training_assignment(
            db_session,
            organization_id=organization_id,
            employee_id=employee_id,
            actor_user_id=admin_id,
            payload=TrainingAssignmentCreate(reason="Rollback proof"),
            idempotency_key="assignment-rollback",
            now=FIXED_NOW,
            request_id=uuid4(),
        )
    monkeypatch.setattr(db_session, "commit", original_commit)

    db_session.expire_all()
    for model in (TrainingAssignment, BackgroundJob, AuditEvent, ApiIdempotencyRecord):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0
