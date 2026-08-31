from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AuditEvent,
    EmployeeProfile,
    OrganizationMembership,
    QuestionVersion,
    SubmittedAnswer,
    TrainingAssignment,
)
from app.schemas.assessment import (
    PracticeAttemptOptionResponse,
    PracticeAttemptQuestionResponse,
    PracticeAttemptResponse,
    PracticeAttemptStartResponse,
    PracticeAttemptTakeoverResponse,
    PracticeSavedAnswerResponse,
    PracticeSummaryResponse,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_attempts import (
    ATTEMPT_INACTIVITY,
    PoolCandidate,
    _previous_order,
    _require_active_training_participation,
    _snapshot_question,
    select_attempt_questions,
)


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _not_ready() -> APIError:
    return _error(409, "ASSESSMENT_NOT_READY", "Практика ще готується.")


async def _owned_practice_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    attempt_id: UUID,
    lock: bool = False,
) -> AssessmentAttempt:
    query = (
        select(AssessmentAttempt)
        .join(
            AssessmentVersion,
            AssessmentVersion.id == AssessmentAttempt.assessment_version_id,
        )
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            AssessmentAttempt.id == attempt_id,
            AssessmentAttempt.organization_id == organization_id,
            AssessmentAttempt.location_id == location_id,
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            Assessment.assessment_type == "whole_menu_knowledge_check",
        )
    )
    if lock:
        query = query.with_for_update(of=AssessmentAttempt)
    attempt = await db.scalar(query)
    if attempt is None:
        raise _not_found()
    return attempt


async def _practice_attempt_response(
    db: AsyncSession,
    attempt: AssessmentAttempt,
    *,
    session_id: UUID,
) -> PracticeAttemptResponse:
    lease = await db.scalar(
        select(AttemptDeviceLease).where(AttemptDeviceLease.attempt_id == attempt.id)
    )
    if lease is None:
        raise RuntimeError("Practice attempt device lease is unavailable")
    question_rows = list(
        await db.scalars(
            select(AttemptQuestion)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    )
    questions: list[PracticeAttemptQuestionResponse] = []
    answered_count = 0
    for question in question_rows:
        options = list(
            await db.scalars(
                select(AttemptOption)
                .where(AttemptOption.attempt_question_id == question.id)
                .order_by(AttemptOption.position)
            )
        )
        saved = await db.scalar(
            select(SubmittedAnswer).where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.attempt_question_id == question.id,
            )
        )
        saved_response = None
        if saved is not None:
            answered_count += 1
            saved_response = PracticeSavedAnswerResponse(
                id=saved.id,
                answer_payload=saved.answer_payload,
                submitted_at=saved.submitted_at,
            )
        questions.append(
            PracticeAttemptQuestionResponse(
                id=question.id,
                position=question.position,
                mechanic=question.mechanic,
                prompt_payload=question.prompt_payload,
                coverage_key=question.coverage_key,
                options=[
                    PracticeAttemptOptionResponse(
                        id=option.id,
                        position=option.position,
                        payload=option.payload,
                    )
                    for option in options
                ],
                saved_answer=saved_response,
            )
        )
    return PracticeAttemptResponse(
        id=attempt.id,
        assignment_id=attempt.assignment_id,
        assessment_version_id=attempt.assessment_version_id,
        status=attempt.status,
        presentation_locale=attempt.presentation_locale,
        started_at=attempt.started_at,
        last_activity_at=attempt.last_activity_at,
        expires_at=attempt.expires_at,
        lease_generation=lease.generation,
        writable=attempt.status == "in_progress" and lease.session_id == session_id,
        answered_count=answered_count,
        questions=questions,
    )


async def get_practice_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    attempt_id: UUID,
    session_id: UUID,
) -> PracticeAttemptResponse:
    attempt = await _owned_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
    )
    return await _practice_attempt_response(db, attempt, session_id=session_id)


async def _current_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    lock: bool = False,
) -> TrainingAssignment | None:
    query = select(TrainingAssignment).where(
        TrainingAssignment.organization_id == organization_id,
        TrainingAssignment.location_id == location_id,
        TrainingAssignment.employee_profile_id == employee_profile_id,
        TrainingAssignment.status != "revoked",
    )
    if lock:
        query = query.with_for_update()
    return cast(TrainingAssignment | None, await db.scalar(query))


async def _practice_ready(
    db: AsyncSession,
    assignment: TrainingAssignment,
) -> tuple[AssessmentVersion, AssessmentReadiness] | None:
    row = (
        await db.execute(
            select(AssessmentVersion, AssessmentReadiness)
            .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
            .join(
                AssessmentReadiness,
                AssessmentReadiness.assessment_version_id == AssessmentVersion.id,
            )
            .where(
                Assessment.training_id == assignment.training_id,
                Assessment.assessment_type == "whole_menu_knowledge_check",
                AssessmentVersion.training_version_id == assignment.training_version_id,
                AssessmentVersion.status == "published",
            )
        )
    ).first()
    if row is None:
        return None
    return row._tuple()


async def get_practice_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    session_id: UUID,
) -> PracticeSummaryResponse:
    # Локальний імпорт розриває цикл: result-сервіс повторно використовує ownership цієї спроби.
    from app.services.practice_results import get_practice_history

    history = await get_practice_history(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    participation = await db.scalar(
        select(OrganizationMembership.training_participation_status)
        .join(EmployeeProfile, EmployeeProfile.membership_id == OrganizationMembership.id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
            EmployeeProfile.id == employee_profile_id,
            EmployeeProfile.location_id == location_id,
        )
    )
    assignment = await _current_assignment(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    if participation is None or assignment is None:
        return PracticeSummaryResponse(
            availability="no_assignment",
            can_start=False,
            reason_codes=["ASSIGNMENT_UNAVAILABLE"],
            readiness_status=None,
            active_attempt=None,
            qualified=history.qualified,
            latest=history.latest,
            best=history.best,
        )
    ready_row = await _practice_ready(db, assignment)
    active_attempt = None
    if ready_row is not None:
        version, _readiness = ready_row
        active = await db.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.employee_profile_id == employee_profile_id,
                AssessmentAttempt.assignment_id == assignment.id,
                AssessmentAttempt.assessment_version_id == version.id,
                AssessmentAttempt.status == "in_progress",
            )
        )
        if active is not None:
            active_attempt = await _practice_attempt_response(db, active, session_id=session_id)
    if participation == "paused":
        return PracticeSummaryResponse(
            availability="paused",
            can_start=False,
            reason_codes=["TRAINING_PAUSED"],
            readiness_status=ready_row[1].status if ready_row is not None else None,
            active_attempt=active_attempt,
            qualified=history.qualified,
            latest=history.latest,
            best=history.best,
        )
    if assignment.status != "completed":
        return PracticeSummaryResponse(
            availability="training_incomplete",
            can_start=False,
            reason_codes=["TRAINING_INCOMPLETE"],
            readiness_status=ready_row[1].status if ready_row is not None else None,
            active_attempt=active_attempt,
            qualified=history.qualified,
            latest=history.latest,
            best=history.best,
        )
    if ready_row is None or ready_row[1].status not in {"ready", "warning"}:
        return PracticeSummaryResponse(
            availability="preparing",
            can_start=False,
            reason_codes=["ASSESSMENT_NOT_READY"],
            readiness_status=ready_row[1].status if ready_row is not None else None,
            active_attempt=active_attempt,
            qualified=history.qualified,
            latest=history.latest,
            best=history.best,
        )
    return PracticeSummaryResponse(
        availability="ready",
        can_start=True,
        reason_codes=[],
        readiness_status=ready_row[1].status,
        active_attempt=active_attempt,
        qualified=history.qualified,
        latest=history.latest,
        best=history.best,
    )


async def start_or_resume_practice_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    presentation_locale: str,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> PracticeAttemptStartResponse:
    await _require_active_training_participation(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    fingerprint = request_fingerprint({"presentation_locale": presentation_locale})
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="practice_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        replay_attempt = await _owned_practice_attempt(
            db,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            attempt_id=replay.resource_id,
        )
        return PracticeAttemptStartResponse(
            attempt=await _practice_attempt_response(db, replay_attempt, session_id=session_id),
            created=False,
            replayed=True,
        )
    assignment = await _current_assignment(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lock=True,
    )
    if assignment is None:
        raise _not_found()
    if assignment.status != "completed":
        raise _error(409, "PRACTICE_UNAVAILABLE", "Спочатку завершіть навчання.")
    ready_row = await _practice_ready(db, assignment)
    if ready_row is None or ready_row[1].status not in {"ready", "warning"}:
        raise _not_ready()
    assessment_version, _readiness = ready_row
    attempt = await db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            AssessmentAttempt.assignment_id == assignment.id,
            AssessmentAttempt.assessment_version_id == assessment_version.id,
            AssessmentAttempt.status == "in_progress",
        )
    )
    created = False
    if attempt is not None and now >= attempt.expires_at:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
        await db.flush()
        attempt = None
    if attempt is None:
        pool_rows = list(
            (
                await db.execute(
                    select(AssessmentQuestionPool, QuestionVersion)
                    .join(
                        QuestionVersion,
                        QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                    )
                    .where(
                        AssessmentQuestionPool.assessment_version_id == assessment_version.id,
                        AssessmentQuestionPool.eligible.is_(True),
                        QuestionVersion.status == "published",
                    )
                )
            ).all()
        )
        selected = select_attempt_questions(
            [
                PoolCandidate(
                    question_version_id=question.id,
                    coverage_key=pool.coverage_key,
                    mechanic=pool.mechanic,
                )
                for pool, question in pool_rows
            ],
            previous_order=await _previous_order(
                db,
                employee_profile_id=employee_profile_id,
                assessment_version_id=assessment_version.id,
            ),
            question_count=10,
        )
        if len(selected) != 10:
            raise _not_ready()
        row_by_id = {question.id: (pool, question) for pool, question in pool_rows}
        attempt = AssessmentAttempt(
            organization_id=organization_id,
            location_id=location_id,
            training_id=assignment.training_id,
            employee_profile_id=employee_profile_id,
            assignment_id=assignment.id,
            assessment_version_id=assessment_version.id,
            status="in_progress",
            presentation_locale=presentation_locale,
            question_count=10,
            snapshot_schema_version=1,
            started_at=now,
            last_activity_at=now,
            expires_at=now + ATTEMPT_INACTIVITY,
        )
        db.add(attempt)
        await db.flush()
        for position, selected_row in enumerate(selected):
            pool, question = row_by_id[selected_row.question_version_id]
            await _snapshot_question(
                db,
                attempt=attempt,
                pool=pool,
                question_version=question,
                position=position,
            )
        db.add(
            AttemptDeviceLease(
                attempt_id=attempt.id,
                session_id=session_id,
                generation=1,
                acquired_at=now,
                last_seen_at=now,
            )
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="practice_attempt_started",
                target_type="assessment_attempt",
                target_id=attempt.id,
                old_values=None,
                new_values={
                    "assessment_version_id": str(assessment_version.id),
                    "question_count": 10,
                    "presentation_locale": presentation_locale,
                },
                request_id=request_id,
                outcome="success",
            )
        )
        created = True
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="practice_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        response_status=200,
        now=now,
    )
    await db.commit()
    return PracticeAttemptStartResponse(
        attempt=await _practice_attempt_response(db, attempt, session_id=session_id),
        created=created,
        replayed=False,
    )


async def takeover_practice_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    attempt_id: UUID,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> PracticeAttemptTakeoverResponse:
    await _require_active_training_participation(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    fingerprint = request_fingerprint({"attempt_id": str(attempt_id)})
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="practice_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    attempt = await _owned_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        lock=replay is None,
    )
    lease = await db.scalar(
        select(AttemptDeviceLease)
        .where(AttemptDeviceLease.attempt_id == attempt.id)
        .with_for_update()
    )
    if lease is None:
        raise RuntimeError("Practice attempt device lease is unavailable")
    if replay is not None:
        return PracticeAttemptTakeoverResponse(
            attempt_id=attempt.id,
            lease_generation=lease.generation,
            replayed=True,
        )
    if attempt.status != "in_progress":
        raise _error(409, "ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    if now >= attempt.expires_at:
        raise _error(409, "ATTEMPT_EXPIRED", "Час активності спроби вичерпано.")
    lease.session_id = session_id
    lease.generation += 1
    lease.acquired_at = now
    lease.last_seen_at = now
    attempt.last_activity_at = now
    attempt.expires_at = now + ATTEMPT_INACTIVITY
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="practice_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="practice_attempt_taken_over",
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values=None,
            new_values={"lease_generation": lease.generation},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return PracticeAttemptTakeoverResponse(
        attempt_id=attempt.id,
        lease_generation=lease.generation,
        replayed=False,
    )
