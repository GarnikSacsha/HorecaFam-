from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentEligibility,
    AssessmentVersion,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AttemptResult,
    AuditEvent,
    SubmittedAnswer,
    TrainingAssignment,
)
from app.schemas.assessment import (
    PracticeAttemptOptionResponse,
    PracticeFinishResponse,
    PracticeHistoryResponse,
    PracticeQuestionReviewResponse,
    PracticeResultResponse,
    PracticeResultSummaryResponse,
    PracticeSavedAnswerResponse,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_answers import _membership_state, knowledge_level
from app.services.practice_attempts import _owned_practice_attempt

HISTORY_LIMIT = 20


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


async def has_final_exam_eligibility(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
) -> bool:
    eligibility_id = await db.scalar(
        select(AssessmentEligibility.id)
        .join(Assessment, Assessment.id == AssessmentEligibility.target_assessment_id)
        .where(
            AssessmentEligibility.employee_profile_id == assignment.employee_profile_id,
            AssessmentEligibility.assignment_id == assignment.id,
            AssessmentEligibility.status == "earned",
            Assessment.assessment_type == "menu_final_exam",
        )
        .limit(1)
    )
    return eligibility_id is not None


def _summary(
    attempt: AssessmentAttempt,
    result: AttemptResult,
) -> PracticeResultSummaryResponse:
    return PracticeResultSummaryResponse(
        result_id=result.id,
        attempt_id=attempt.id,
        assessment_version_id=attempt.assessment_version_id,
        completed_at=result.completed_at,
        correct_count=result.correct_count,
        total_count=10,
        score_basis_points=result.score_basis_points,
        knowledge_level=result.knowledge_level,
        critical_error_count=result.critical_error_count,
    )


async def get_practice_history(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
) -> PracticeHistoryResponse:
    assignment = await db.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.organization_id == organization_id,
            TrainingAssignment.location_id == location_id,
            TrainingAssignment.employee_profile_id == employee_profile_id,
            TrainingAssignment.status != "revoked",
        )
    )
    if assignment is None:
        return PracticeHistoryResponse(qualified=False, latest=None, best=None, history=[])
    current_version_id = await db.scalar(
        select(AssessmentVersion.id)
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            Assessment.training_id == assignment.training_id,
            Assessment.assessment_type == "whole_menu_knowledge_check",
            AssessmentVersion.training_version_id == assignment.training_version_id,
            AssessmentVersion.status == "published",
        )
        .order_by(AssessmentVersion.version_number.desc())
        .limit(1)
    )
    rows = list(
        (
            await db.execute(
                select(AssessmentAttempt, AttemptResult)
                .join(AttemptResult, AttemptResult.attempt_id == AssessmentAttempt.id)
                .join(
                    AssessmentVersion,
                    AssessmentVersion.id == AssessmentAttempt.assessment_version_id,
                )
                .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
                .where(
                    AssessmentAttempt.organization_id == organization_id,
                    AssessmentAttempt.location_id == location_id,
                    AssessmentAttempt.employee_profile_id == employee_profile_id,
                    AssessmentAttempt.assignment_id == assignment.id,
                    AssessmentAttempt.assessment_version_id == current_version_id,
                    AssessmentAttempt.status == "completed",
                    Assessment.assessment_type == "whole_menu_knowledge_check",
                )
                .order_by(AttemptResult.completed_at.desc(), AttemptResult.id.desc())
            )
        ).all()
    )
    latest = _summary(*rows[0]) if rows else None
    best_row = max(
        rows,
        key=lambda row: (
            row[1].score_basis_points,
            row[1].completed_at,
            str(row[1].id),
        ),
        default=None,
    )
    return PracticeHistoryResponse(
        qualified=await has_final_exam_eligibility(db, assignment=assignment),
        latest=latest,
        best=_summary(*best_row) if best_row is not None else None,
        history=[_summary(*row) for row in rows[:HISTORY_LIMIT]],
    )


async def _finish_response(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
    replayed: bool,
) -> PracticeFinishResponse:
    question_rows = list(
        await db.scalars(
            select(AttemptQuestion)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    )
    review: list[PracticeQuestionReviewResponse] = []
    for question in question_rows:
        options = list(
            await db.scalars(
                select(AttemptOption)
                .where(AttemptOption.attempt_question_id == question.id)
                .order_by(AttemptOption.position)
            )
        )
        answer = await db.scalar(
            select(SubmittedAnswer).where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.attempt_question_id == question.id,
            )
        )
        if answer is None:
            raise RuntimeError("Completed Practice attempt has an unanswered question")
        review.append(
            PracticeQuestionReviewResponse(
                attempt_question_id=question.id,
                position=question.position,
                mechanic=question.mechanic,
                prompt_payload=question.prompt_payload,
                options=[
                    PracticeAttemptOptionResponse(
                        id=option.id,
                        position=option.position,
                        payload=option.payload,
                    )
                    for option in options
                ],
                answer=PracticeSavedAnswerResponse(
                    id=answer.id,
                    answer_payload=answer.answer_payload,
                    submitted_at=answer.submitted_at,
                ),
                is_correct=answer.is_correct,
                correct_option_ids=[option.id for option in options if option.is_correct],
                explanation_payload=question.explanation_payload,
                is_critical=question.is_critical,
                is_critical_error=answer.is_critical_error,
            )
        )
    assignment = await db.get(TrainingAssignment, attempt.assignment_id)
    if assignment is None:
        raise RuntimeError("Completed Practice attempt assignment is unavailable")
    earned_by_attempt = (
        await db.scalar(
            select(AssessmentEligibility.id).where(
                AssessmentEligibility.earned_by_attempt_id == attempt.id,
                AssessmentEligibility.status == "earned",
            )
        )
        is not None
    )
    return PracticeFinishResponse(
        result=PracticeResultResponse(
            id=result.id,
            correct_count=result.correct_count,
            total_count=10,
            score_basis_points=result.score_basis_points,
            knowledge_level=result.knowledge_level,
            pass_status=None,
            critical_error_count=result.critical_error_count,
            completed_at=result.completed_at,
        ),
        qualified=await has_final_exam_eligibility(db, assignment=assignment),
        eligibility_earned=earned_by_attempt,
        review=review,
        replayed=replayed,
    )


async def _finish_practice_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    attempt_id: UUID,
    lease_generation: int,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> PracticeFinishResponse:
    attempt = await _owned_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        lock=True,
    )
    fingerprint = request_fingerprint(
        {"attempt_id": str(attempt.id), "lease_generation": lease_generation}
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="practice_attempt_finish",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        result = await db.get(AttemptResult, replay.resource_id)
        if result is None or result.attempt_id != attempt.id:
            raise RuntimeError("Practice finish replay resource is unavailable")
        return await _finish_response(db, attempt=attempt, result=result, replayed=True)

    membership_state = await _membership_state(db, employee_profile_id)
    if membership_state is None or membership_state[0] != "active":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба зараз недоступна для завершення.")
    if membership_state[1] == "paused":
        # Пауза заморожує семиденне вікно, але не дозволяє завершити спробу.
        attempt.last_activity_at = now
        attempt.expires_at = now + timedelta(days=7)
        await db.commit()
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спробу призупинено адміністратором.")
    if attempt.status == "completed":
        raise _error(409, "ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    if attempt.status == "expired" or now >= attempt.expires_at:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
        await db.commit()
        raise _error(409, "ATTEMPT_EXPIRED", "Строк активності спроби минув.")
    if attempt.status != "in_progress":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба більше недоступна для завершення.")

    lease = await db.scalar(
        select(AttemptDeviceLease)
        .where(AttemptDeviceLease.attempt_id == attempt.id)
        .with_for_update()
    )
    if lease is None or lease.session_id != session_id or lease.generation != lease_generation:
        raise _error(409, "ATTEMPT_DEVICE_CONFLICT", "Інша сесія має право запису до цієї спроби.")
    assignment = await db.scalar(
        select(TrainingAssignment)
        .where(TrainingAssignment.id == attempt.assignment_id)
        .with_for_update()
    )
    if assignment is None or assignment.status != "completed":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Навчання більше не дозволяє завершити спробу.")
    answer_count = (
        await db.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(SubmittedAnswer.attempt_id == attempt.id)
        )
        or 0
    )
    if answer_count != 10:
        raise _error(409, "PRACTICE_INCOMPLETE", "Потрібно відповісти на всі 10 запитань.")

    correct_count = (
        await db.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.is_correct.is_(True),
            )
        )
        or 0
    )
    critical_error_count = (
        await db.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.is_critical_error.is_(True),
            )
        )
        or 0
    )
    score_basis_points = correct_count * 1000
    result = AttemptResult(
        attempt_id=attempt.id,
        correct_count=correct_count,
        total_count=10,
        score_basis_points=score_basis_points,
        knowledge_level=knowledge_level(score_basis_points),
        pass_status=None,
        critical_error_count=critical_error_count,
        section_breakdown={},
        completed_at=now,
    )
    db.add(result)
    attempt.status = "completed"
    attempt.completed_at = now
    attempt.last_activity_at = now
    lease.last_seen_at = now
    await db.flush()

    target_assessment = await db.scalar(
        select(Assessment).where(
            Assessment.organization_id == organization_id,
            Assessment.location_id == location_id,
            Assessment.training_id == assignment.training_id,
            Assessment.assessment_type == "menu_final_exam",
        )
    )
    if target_assessment is None:
        raise _error(409, "FINAL_EXAM_NOT_CONFIGURED", "Підсумковий іспит ще не налаштовано.")
    eligibility = await db.scalar(
        select(AssessmentEligibility).where(
            AssessmentEligibility.employee_profile_id == employee_profile_id,
            AssessmentEligibility.assignment_id == assignment.id,
            AssessmentEligibility.target_assessment_id == target_assessment.id,
            AssessmentEligibility.status == "earned",
        )
    )
    eligibility_earned = correct_count >= 4 and eligibility is None
    if eligibility_earned:
        db.add(
            AssessmentEligibility(
                organization_id=organization_id,
                location_id=location_id,
                training_id=assignment.training_id,
                employee_profile_id=employee_profile_id,
                assignment_id=assignment.id,
                target_assessment_id=target_assessment.id,
                earned_by_attempt_id=attempt.id,
                status="earned",
                earned_at=now,
            )
        )
        await db.flush()
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="practice_attempt_finish",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="attempt_result",
        resource_id=result.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="practice_attempt_finished",
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values={"status": "in_progress"},
            new_values={
                "status": "completed",
                "correct_count": correct_count,
                "score_basis_points": score_basis_points,
                "critical_error_count": critical_error_count,
                "eligibility_earned": eligibility_earned,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return await _finish_response(db, attempt=attempt, result=result, replayed=False)


async def finish_practice_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    attempt_id: UUID,
    lease_generation: int,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> PracticeFinishResponse:
    try:
        return await _finish_practice_attempt(
            db,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            attempt_id=attempt_id,
            lease_generation=lease_generation,
            idempotency_key=idempotency_key,
            request_id=request_id,
            now=now,
        )
    except Exception:
        await db.rollback()
        raise
