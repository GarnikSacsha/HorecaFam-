from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiIdempotencyRecord, AuditEvent, BackgroundJob, TrainingAssignment
from app.schemas.training import TrainingAssignmentCreate
from app.services.training_assignments import create_training_assignment
from app.services.training_progress import derive_training_progress
from tests.api.test_menu_admin_api import FIXED_NOW
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_user,
)
from tests.factories.training import (
    make_lesson,
    make_lesson_completion,
    make_lesson_version,
    make_training,
    make_training_assignment,
    make_training_module,
    make_training_module_version,
    make_training_version,
)


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


async def test_progress_uses_required_stable_lessons_and_floor_division(
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Progress organization")
    location = make_location(organization)
    user = make_user(email_normalized="progress-employee@example.com")
    membership = make_membership(organization, user, activated_at=FIXED_NOW)
    db_session.add_all([organization, location, user, membership])
    await db_session.flush()
    employee = make_employee_profile(membership, organization.id, location_id=location.id)
    training = make_training(organization.id, location.id)
    db_session.add_all([employee, training])
    await db_session.flush()
    version = make_training_version(
        training,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=FIXED_NOW,
    )
    module = make_training_module(training)
    db_session.add_all([version, module])
    await db_session.flush()
    module_version = make_training_module_version(version, module)
    first = make_lesson(module)
    second = make_lesson(module)
    optional = make_lesson(module)
    db_session.add_all([module_version, first, second, optional])
    await db_session.flush()
    first_version = make_lesson_version(module_version, first, position=0, required=True)
    second_version = make_lesson_version(module_version, second, position=1, required=True)
    optional_version = make_lesson_version(module_version, optional, position=2, required=False)
    assignment = make_training_assignment(employee, training, version)
    db_session.add_all([first_version, second_version, optional_version, assignment])
    await db_session.flush()
    db_session.add_all(
        [
            make_lesson_completion(assignment, first_version, user.id),
            make_lesson_completion(assignment, optional_version, user.id),
        ]
    )
    await db_session.commit()

    progress = await derive_training_progress(db_session, assignment=assignment)

    assert progress.model_dump() == {
        "required_lesson_count": 2,
        "completed_required_lesson_count": 1,
        "percentage": 50,
        "is_complete": False,
    }
