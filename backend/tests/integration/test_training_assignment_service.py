from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    ApiIdempotencyRecord,
    AuditEvent,
    BackgroundJob,
    LessonCompletion,
    TrainingAssignment,
)
from app.schemas.training import TrainingAssignmentCreate
from app.services.training_assignments import create_training_assignment
from app.services.training_completion import complete_employee_training_lesson
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


@dataclass(frozen=True)
class CompletionGraph:
    organization_id: UUID
    location_id: UUID
    user_id: UUID
    employee_id: UUID
    assignment_id: UUID
    lesson_ids: list[UUID]


async def arrange_completion_graph(
    db: AsyncSession,
    *,
    required_count: int,
) -> CompletionGraph:
    organization = make_organization(name=f"Completion organization {uuid4()}")
    location = make_location(organization)
    user = make_user(email_normalized=f"completion-{uuid4()}@example.com")
    membership = make_membership(organization, user, activated_at=FIXED_NOW)
    db.add_all([organization, location, user, membership])
    await db.flush()
    employee = make_employee_profile(membership, organization.id, location_id=location.id)
    training = make_training(organization.id, location.id)
    db.add_all([employee, training])
    await db.flush()
    version = make_training_version(
        training,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=FIXED_NOW,
    )
    module = make_training_module(training)
    db.add_all([version, module])
    await db.flush()
    module_version = make_training_module_version(version, module)
    lessons = [make_lesson(module) for _ in range(required_count)]
    db.add_all([module_version, *lessons])
    await db.flush()
    lesson_versions = [
        make_lesson_version(module_version, lesson, position=position, required=True)
        for position, lesson in enumerate(lessons)
    ]
    assignment = make_training_assignment(
        employee,
        training,
        version,
        assigned_at=FIXED_NOW,
    )
    db.add_all([*lesson_versions, assignment])
    await db.commit()
    return CompletionGraph(
        organization_id=organization.id,
        location_id=location.id,
        user_id=user.id,
        employee_id=employee.id,
        assignment_id=assignment.id,
        lesson_ids=[lesson.lesson_id for lesson in lesson_versions],
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


async def test_explicit_completion_transitions_assignment_from_in_progress_to_completed(
    db_session: AsyncSession,
) -> None:
    graph = await arrange_completion_graph(db_session, required_count=2)

    first = await complete_employee_training_lesson(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        employee_profile_id=graph.employee_id,
        actor_user_id=graph.user_id,
        lesson_id=graph.lesson_ids[0],
        idempotency_key="completion-transition-first",
        now=FIXED_NOW,
        request_id=uuid4(),
    )
    with pytest.raises(APIError) as reused:
        await complete_employee_training_lesson(
            db_session,
            organization_id=graph.organization_id,
            location_id=graph.location_id,
            employee_profile_id=graph.employee_id,
            actor_user_id=graph.user_id,
            lesson_id=graph.lesson_ids[1],
            idempotency_key="completion-transition-first",
            now=FIXED_NOW,
            request_id=uuid4(),
        )
    assert reused.value.code == "IDEMPOTENCY_KEY_REUSED"
    second = await complete_employee_training_lesson(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        employee_profile_id=graph.employee_id,
        actor_user_id=graph.user_id,
        lesson_id=graph.lesson_ids[1],
        idempotency_key="completion-transition-second",
        now=FIXED_NOW,
        request_id=uuid4(),
    )

    assert first.assignment.status == "in_progress"
    assert first.assignment.started_at == FIXED_NOW
    assert first.assignment.completed_at is None
    assert first.progress.percentage == 50
    assert first.next_action == "open_lesson"
    assert second.assignment.status == "completed"
    assert second.assignment.started_at == FIXED_NOW
    assert second.assignment.completed_at == FIXED_NOW
    assert second.progress.percentage == 100
    assert second.next_action == "review_training"
    assert await db_session.scalar(select(func.count()).select_from(LessonCompletion)) == 2


async def test_completion_rolls_back_fact_assignment_audit_and_idempotency(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = await arrange_completion_graph(db_session, required_count=1)
    original_commit = db_session.commit

    async def fail_commit() -> None:
        raise RuntimeError("forced test-only completion commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced test-only completion commit failure"):
        await complete_employee_training_lesson(
            db_session,
            organization_id=graph.organization_id,
            location_id=graph.location_id,
            employee_profile_id=graph.employee_id,
            actor_user_id=graph.user_id,
            lesson_id=graph.lesson_ids[0],
            idempotency_key="completion-rollback",
            now=FIXED_NOW,
            request_id=uuid4(),
        )
    monkeypatch.setattr(db_session, "commit", original_commit)
    db_session.expire_all()

    stored_assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    assert stored_assignment.status == "assigned"
    assert stored_assignment.started_at is None
    assert stored_assignment.completed_at is None
    assert await db_session.scalar(select(func.count()).select_from(LessonCompletion)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_lesson_completed")
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(ApiIdempotencyRecord)
            .where(ApiIdempotencyRecord.action == "training_lesson.complete")
        )
        == 0
    )
