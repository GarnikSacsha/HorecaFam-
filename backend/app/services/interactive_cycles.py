from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentVersion,
    AttemptQuestion,
    AuditEvent,
    EmployeeProfile,
    LessonQuestionCycle,
    LessonQuestionCycleItem,
    QuestionVersion,
    SubmittedAnswer,
    TrainingAssignment,
)
from app.schemas.assessment import LessonQuestionCycleResponse
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)


async def lock_employee(
    db: AsyncSession, organization_id: UUID, location_id: UUID, employee_id: UUID
) -> None:
    employee = await db.scalar(
        select(EmployeeProfile.id)
        .where(
            EmployeeProfile.id == employee_id,
            EmployeeProfile.organization_id == organization_id,
            EmployeeProfile.location_id == location_id,
        )
        .with_for_update()
    )
    if employee is None:
        raise APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


async def current_cycle(
    db: AsyncSession, employee_id: UUID, lesson_id: UUID
) -> LessonQuestionCycle | None:
    return cast(
        LessonQuestionCycle | None,
        await db.scalar(
            select(LessonQuestionCycle).where(
                LessonQuestionCycle.employee_profile_id == employee_id,
                LessonQuestionCycle.lesson_id == lesson_id,
                LessonQuestionCycle.ended_at.is_(None),
            )
        ),
    )


async def lesson_attempts(
    db: AsyncSession, organization_id: UUID, location_id: UUID, employee_id: UUID, lesson_id: UUID
) -> list[AssessmentAttempt]:
    return list(
        await db.scalars(
            select(AssessmentAttempt)
            .join(
                AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id
            )
            .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
            .where(
                AssessmentAttempt.organization_id == organization_id,
                AssessmentAttempt.location_id == location_id,
                AssessmentAttempt.employee_profile_id == employee_id,
                AssessmentVersion.lesson_id == lesson_id,
                Assessment.assessment_type == "interactive_training",
            )
            .order_by(AssessmentAttempt.started_at, AssessmentAttempt.id)
        )
    )


async def resumable_attempt(
    db: AsyncSession, attempts: list[AssessmentAttempt], now: datetime
) -> AssessmentAttempt | None:
    for attempt in attempts:
        if attempt.status != "in_progress" or now >= attempt.expires_at:
            continue
        assignment = await db.get(TrainingAssignment, attempt.assignment_id)
        if assignment is not None and (
            assignment.status != "revoked"
            or (assignment.revoke_reason == "rollout" and assignment.source_rollout_id is not None)
        ):
            return attempt
    return None


async def legacy_items(
    db: AsyncSession, attempts: list[AssessmentAttempt]
) -> list[tuple[UUID, UUID, UUID, str]]:
    if not attempts:
        return []
    rows = (
        await db.execute(
            select(AttemptQuestion, QuestionVersion.question_id, SubmittedAnswer.id)
            .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
            .outerjoin(SubmittedAnswer, SubmittedAnswer.attempt_question_id == AttemptQuestion.id)
            .where(AttemptQuestion.attempt_id.in_([a.id for a in attempts]))
            .order_by(SubmittedAnswer.id.is_(None), AttemptQuestion.id)
        )
    ).all()
    active = {a.id for a in attempts if a.status == "in_progress"}
    seen: set[UUID] = set()
    result = []
    for question, question_id, _answer in rows:
        if question_id not in seen:
            seen.add(question_id)
            result.append(
                (
                    question_id,
                    question.question_version_id,
                    question.id,
                    "reserved" if question.attempt_id in active else "legacy",
                )
            )
    return result


async def ensure_cycle(
    db: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    employee_id: UUID,
    lesson_id: UUID,
    now: datetime,
) -> LessonQuestionCycle:
    cycle = await current_cycle(db, employee_id, lesson_id)
    if cycle is not None:
        return cycle
    cycle = LessonQuestionCycle(
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_id,
        lesson_id=lesson_id,
        number=1,
        created_at=now,
    )
    db.add(cycle)
    await db.flush()
    attempts = await lesson_attempts(db, organization_id, location_id, employee_id, lesson_id)
    for question_id, version_id, snapshot_id, origin in await legacy_items(db, attempts):
        db.add(
            LessonQuestionCycleItem(
                cycle_id=cycle.id,
                question_id=question_id,
                question_version_id=version_id,
                attempt_question_id=snapshot_id,
                origin=origin,
            )
        )
    await db.flush()
    return cycle


async def cycle_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_id: UUID,
    lesson_id: UUID,
    assessment_version_id: UUID | None,
    now: datetime | None = None,
    cycle: LessonQuestionCycle | None = None,
) -> LessonQuestionCycleResponse:
    now = now or datetime.now(UTC)
    cycle = cycle or await current_cycle(db, employee_id, lesson_id)
    attempts = await lesson_attempts(db, organization_id, location_id, employee_id, lesson_id)
    if cycle is None:
        entries = await legacy_items(db, attempts)
    else:
        items = list(
            await db.scalars(
                select(LessonQuestionCycleItem).where(LessonQuestionCycleItem.cycle_id == cycle.id)
            )
        )
        entries = [
            (i.question_id, i.question_version_id, i.attempt_question_id, i.origin) for i in items
        ]
    used = {q for q, _v, _s, _o in entries}
    eligible = (
        set(
            await db.scalars(
                select(QuestionVersion.question_id)
                .join(
                    AssessmentQuestionPool,
                    AssessmentQuestionPool.question_version_id == QuestionVersion.id,
                )
                .where(
                    AssessmentQuestionPool.assessment_version_id == assessment_version_id,
                    AssessmentQuestionPool.eligible.is_(True),
                    QuestionVersion.status == "published",
                )
            )
        )
        if assessment_version_id
        else set()
    )
    snapshot_ids = [s for _q, _v, s, _o in entries]
    answered = (
        set(
            await db.scalars(
                select(SubmittedAnswer.attempt_question_id).where(
                    SubmittedAnswer.attempt_question_id.in_(snapshot_ids)
                )
            )
        )
        if snapshot_ids
        else set()
    )
    pending = [s for _q, _v, s, origin in entries if origin == "reserved" and s not in answered]
    active = await resumable_attempt(db, attempts, now)
    remaining = len(eligible - used)
    # Історичний незавершений знімок не означає, що працівник відповів на всі питання.
    if remaining == 0 and len(answered) < len(entries):
        pending = snapshot_ids
    status = (
        "in_progress"
        if active
        else "restart_required"
        if pending
        else "available"
        if remaining
        else "exhausted"
    )
    return LessonQuestionCycleResponse(
        id=cycle.id if cycle else None,
        number=cycle.number if cycle else 1,
        status=status,
        eligible_count=len(eligible),
        answered_count=len(answered),
        reserved_count=len(used),
        remaining_count=remaining,
        can_restart=bool(eligible) and status in {"exhausted", "restart_required"},
    )


async def restart_lesson_cycle(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    lesson_id: UUID,
    expected_cycle_id: UUID | None,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> LessonQuestionCycleResponse:
    # Імпорт локальний: старт використовує той самий модуль обліку циклів.
    from app.services.interactive_attempts import (
        _assessment_ready,
        _assignment_lesson,
        _require_active_training_participation,
    )

    await lock_employee(db, organization_id, location_id, employee_profile_id)
    await _require_active_training_participation(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    assignment, lesson = await _assignment_lesson(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lesson_id=lesson_id,
    )
    assessment, _ = await _assessment_ready(db, assignment=assignment, lesson_version=lesson)
    fingerprint = request_fingerprint(
        {"lesson_id": str(lesson_id), "expected_cycle_id": str(expected_cycle_id)}
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="interactive_cycle_restart",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        replay_cycle = await db.get(LessonQuestionCycle, replay.resource_id)
        if replay_cycle is None:
            raise RuntimeError("Cycle replay is unavailable")
        return await cycle_summary(
            db,
            organization_id=organization_id,
            location_id=location_id,
            employee_id=employee_profile_id,
            lesson_id=lesson_id,
            assessment_version_id=assessment.id,
            now=now,
            cycle=replay_cycle,
        )
    current = await current_cycle(db, employee_profile_id, lesson_id)
    if expected_cycle_id is not None:
        supplied = await db.get(LessonQuestionCycle, expected_cycle_id)
        if (
            supplied is None
            or supplied.employee_profile_id != employee_profile_id
            or supplied.lesson_id != lesson_id
        ):
            raise APIError(
                status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено."
            )
    if (current.id if current else None) != expected_cycle_id:
        raise APIError(
            status_code=409, code="REVISION_CONFLICT", message="Цикл змінився. Оновіть сторінку."
        )
    state = await cycle_summary(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_id=employee_profile_id,
        lesson_id=lesson_id,
        assessment_version_id=assessment.id,
        now=now,
    )
    if not state.can_restart:
        raise APIError(
            status_code=409,
            code="INTERACTIVE_CYCLE_IN_PROGRESS",
            message="Спочатку завершіть поточний цикл.",
        )
    current = await ensure_cycle(
        db, organization_id, location_id, employee_profile_id, lesson_id, now
    )
    current.ended_at = now
    for attempt in await lesson_attempts(
        db, organization_id, location_id, employee_profile_id, lesson_id
    ):
        if attempt.status == "in_progress" and now >= attempt.expires_at:
            attempt.status = "expired"
    await db.flush()
    cycle = LessonQuestionCycle(
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lesson_id=lesson_id,
        number=current.number + 1,
        created_at=now,
    )
    db.add(cycle)
    await db.flush()
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="interactive_cycle_restart",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="lesson_question_cycle",
        resource_id=cycle.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="interactive_cycle_restarted",
            target_type="lesson_question_cycle",
            target_id=cycle.id,
            old_values={"cycle_id": str(current.id)},
            new_values={"number": cycle.number},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return await cycle_summary(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_id=employee_profile_id,
        lesson_id=lesson_id,
        assessment_version_id=assessment.id,
        now=now,
        cycle=cycle,
    )
