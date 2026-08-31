from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    ApiIdempotencyRecord,
    AuditEvent,
    EmployeeProfile,
    LessonCompletion,
    LessonVersion,
    OrganizationMembership,
    TrainingAssignment,
    TrainingModuleVersion,
)
from app.schemas.training import (
    EmployeeTrainingAssignmentSummary,
    LessonCompletionResponse,
    LessonCompletionSummary,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.practice_results import has_final_exam_eligibility
from app.services.training_progress import derive_training_progress


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def _completion_not_allowed() -> APIError:
    return APIError(
        status_code=409,
        code="TRAINING_COMPLETION_NOT_ALLOWED",
        message="Завершення уроку зараз недоступне.",
    )


def _assignment_summary(assignment: TrainingAssignment) -> EmployeeTrainingAssignmentSummary:
    return EmployeeTrainingAssignmentSummary(
        id=assignment.id,
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
    )


def _completion_summary(completion: LessonCompletion) -> LessonCompletionSummary:
    return LessonCompletionSummary(
        id=completion.id,
        assignment_id=completion.assignment_id,
        lesson_id=completion.lesson_id,
        lesson_version_id=completion.lesson_version_id,
        completion_source=completion.completion_source,
        completed_at=completion.completed_at,
    )


async def _current_assignment_context(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
) -> tuple[TrainingAssignment, OrganizationMembership]:
    row = (
        (
            await db.execute(
                select(TrainingAssignment, OrganizationMembership)
                .join(
                    EmployeeProfile,
                    and_(
                        EmployeeProfile.id == TrainingAssignment.employee_profile_id,
                        EmployeeProfile.organization_id == TrainingAssignment.organization_id,
                    ),
                )
                .join(
                    OrganizationMembership,
                    and_(
                        OrganizationMembership.id == EmployeeProfile.membership_id,
                        OrganizationMembership.organization_id == EmployeeProfile.organization_id,
                    ),
                )
                .where(
                    TrainingAssignment.organization_id == organization_id,
                    TrainingAssignment.location_id == location_id,
                    TrainingAssignment.employee_profile_id == employee_profile_id,
                    TrainingAssignment.status != "revoked",
                    OrganizationMembership.status == "active",
                )
                .with_for_update()
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        raise _not_found()
    return row


async def _assigned_lesson_version(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    lesson_id: UUID,
) -> LessonVersion:
    lesson_version = await db.scalar(
        select(LessonVersion)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .where(
            TrainingModuleVersion.training_version_id == assignment.training_version_id,
            LessonVersion.lesson_id == lesson_id,
        )
    )
    if lesson_version is None:
        raise _not_found()
    return lesson_version


async def _completion_response(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    completion: LessonCompletion,
) -> LessonCompletionResponse:
    progress = await derive_training_progress(db, assignment=assignment)
    next_action = "open_lesson"
    if progress.is_complete:
        next_action = (
            "review_training"
            if await has_final_exam_eligibility(db, assignment=assignment)
            else "open_practice"
        )
    return LessonCompletionResponse(
        completion=_completion_summary(completion),
        assignment=_assignment_summary(assignment),
        progress=progress,
        next_action=next_action,
    )


async def _idempotent_completion(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    record: ApiIdempotencyRecord,
) -> LessonCompletionResponse:
    if record.resource_type != "lesson_completion":
        raise RuntimeError("Idempotent Lesson Completion target is inconsistent")
    completion = await db.get(LessonCompletion, record.resource_id)
    if completion is None or completion.assignment_id != assignment.id:
        raise RuntimeError("Idempotent Lesson Completion resource is unavailable")
    response = await _completion_response(db, assignment=assignment, completion=completion)
    await db.commit()
    return response


async def _complete_employee_training_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    lesson_id: UUID,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> LessonCompletionResponse:
    assignment, membership = await _current_assignment_context(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    lesson_version = await _assigned_lesson_version(
        db,
        assignment=assignment,
        lesson_id=lesson_id,
    )
    fingerprint = request_fingerprint(
        {"assignment_id": str(assignment.id), "lesson_id": str(lesson_id)}
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_lesson.complete",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        return await _idempotent_completion(db, assignment=assignment, record=replay)

    existing = await db.scalar(
        select(LessonCompletion).where(
            LessonCompletion.assignment_id == assignment.id,
            LessonCompletion.lesson_id == lesson_id,
        )
    )
    if membership.training_participation_status == "paused" and existing is None:
        raise _completion_not_allowed()
    completion_id = existing.id if existing is not None else uuid4()
    decision = await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_lesson.complete",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="lesson_completion",
        resource_id=completion_id,
        response_status=200,
        now=now,
    )
    if decision.replayed:
        return await _idempotent_completion(db, assignment=assignment, record=decision.record)
    if existing is not None:
        response = await _completion_response(db, assignment=assignment, completion=existing)
        await db.commit()
        return response

    completion = LessonCompletion(
        id=completion_id,
        organization_id=organization_id,
        location_id=location_id,
        training_id=assignment.training_id,
        assignment_id=assignment.id,
        lesson_id=lesson_id,
        lesson_version_id=lesson_version.id,
        completion_source="employee",
        completed_by_user_id=actor_user_id,
        completed_at=now,
    )
    db.add(completion)
    await db.flush()
    progress = await derive_training_progress(db, assignment=assignment)
    old_status = assignment.status
    if assignment.status == "assigned":
        assignment.started_at = now
    if progress.is_complete and assignment.status in ("assigned", "in_progress"):
        assignment.status = "completed"
        assignment.completed_at = now
    elif assignment.status == "assigned":
        assignment.status = "in_progress"
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="training_lesson_completed",
            target_type="lesson_completion",
            target_id=completion.id,
            old_values={"assignment_status": old_status},
            new_values={
                "assignment_id": str(assignment.id),
                "lesson_id": str(lesson_id),
                "assignment_status": assignment.status,
                "progress_percentage": progress.percentage,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return await _completion_response(
        db,
        assignment=assignment,
        completion=completion,
    )


async def complete_employee_training_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    lesson_id: UUID,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> LessonCompletionResponse:
    try:
        return await _complete_employee_training_lesson(
            db,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=actor_user_id,
            lesson_id=lesson_id,
            idempotency_key=idempotency_key,
            now=now,
            request_id=request_id,
        )
    except Exception:
        await db.rollback()
        raise
