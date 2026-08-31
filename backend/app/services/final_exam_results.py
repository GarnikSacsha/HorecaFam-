from datetime import datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
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
    FinalExamAttemptOptionResponse,
    FinalExamFinishResponse,
    FinalExamHistoryResponse,
    FinalExamQuestionReviewResponse,
    FinalExamResultResponse,
    FinalExamResultSummaryResponse,
    FinalExamSavedAnswerResponse,
)
from app.services.final_exam_attempts import (
    _certification,
    _owned_final_exam_attempt,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_answers import _membership_state, knowledge_level

HISTORY_LIMIT = 50


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def final_exam_pass_status(
    correct_count: int, total_count: int = 20
) -> Literal["passed", "failed"]:
    return "passed" if correct_count * 100 >= 70 * total_count else "failed"


def _summary(
    attempt: AssessmentAttempt,
    result: AttemptResult,
) -> FinalExamResultSummaryResponse:
    return FinalExamResultSummaryResponse(
        result_id=result.id,
        attempt_id=attempt.id,
        assessment_version_id=attempt.assessment_version_id,
        completed_at=result.completed_at,
        correct_count=result.correct_count,
        score_basis_points=result.score_basis_points,
        knowledge_level=cast(
            Literal["very_weak", "weak", "good", "strong"], result.knowledge_level
        ),
        pass_status=cast(Literal["passed", "failed"], result.pass_status),
        critical_error_count=result.critical_error_count,
    )


async def get_final_exam_history(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
) -> FinalExamHistoryResponse:
    assignment = await db.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.organization_id == organization_id,
            TrainingAssignment.location_id == location_id,
            TrainingAssignment.employee_profile_id == employee_profile_id,
            TrainingAssignment.status != "revoked",
        )
    )
    if assignment is None:
        return FinalExamHistoryResponse(certification=None, latest=None, best=None, history=[])
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
                    AssessmentAttempt.training_id == assignment.training_id,
                    AssessmentAttempt.status == "completed",
                    Assessment.assessment_type == "menu_final_exam",
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
    return FinalExamHistoryResponse(
        certification=await _certification(
            db,
            employee_profile_id=employee_profile_id,
            training_id=assignment.training_id,
        ),
        latest=latest,
        best=_summary(*best_row) if best_row is not None else None,
        history=[_summary(*row) for row in rows[:HISTORY_LIMIT]],
    )


async def _finish_response(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
    newly_certified: bool,
    replayed: bool,
) -> FinalExamFinishResponse:
    question_rows = list(
        await db.scalars(
            select(AttemptQuestion)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    )
    review: list[FinalExamQuestionReviewResponse] = []
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
            raise RuntimeError("Completed Final Exam attempt has an unanswered question")
        review.append(
            FinalExamQuestionReviewResponse(
                attempt_question_id=question.id,
                position=question.position,
                mechanic=question.mechanic,
                prompt_payload=question.prompt_payload,
                options=[
                    FinalExamAttemptOptionResponse(
                        id=option.id, position=option.position, payload=option.payload
                    )
                    for option in options
                ],
                answer=FinalExamSavedAnswerResponse(
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
    certification = await _certification(
        db,
        employee_profile_id=attempt.employee_profile_id,
        training_id=attempt.training_id,
    )
    pass_status = cast(Literal["passed", "failed"], result.pass_status)
    return FinalExamFinishResponse(
        result=FinalExamResultResponse(
            id=result.id,
            correct_count=result.correct_count,
            score_basis_points=result.score_basis_points,
            knowledge_level=cast(
                Literal["very_weak", "weak", "good", "strong"], result.knowledge_level
            ),
            pass_status=pass_status,
            critical_error_count=result.critical_error_count,
            section_breakdown=result.section_breakdown,
            completed_at=result.completed_at,
        ),
        certification=certification,
        newly_certified=newly_certified,
        retake_available=pass_status == "failed",
        review=review,
        replayed=replayed,
    )


async def _finish_final_exam_attempt(
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
) -> FinalExamFinishResponse:
    attempt = await _owned_final_exam_attempt(
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
        action="final_exam_attempt_finish",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        result = await db.get(AttemptResult, replay.resource_id)
        if result is None or result.attempt_id != attempt.id:
            raise RuntimeError("Final Exam finish replay resource is unavailable")
        return await _finish_response(
            db,
            attempt=attempt,
            result=result,
            newly_certified=False,
            replayed=True,
        )
    membership_state = await _membership_state(db, employee_profile_id)
    if membership_state is None or membership_state[0] != "active":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба зараз недоступна для завершення.")
    if membership_state[1] == "paused":
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
    if answer_count != 20:
        raise _error(409, "ATTEMPT_INCOMPLETE", "Потрібно відповісти на всі 20 запитань.")
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
    breakdown_rows = list(
        (
            await db.execute(
                select(
                    AttemptQuestion.coverage_key,
                    func.count(),
                    func.count().filter(SubmittedAnswer.is_correct.is_(True)),
                )
                .join(
                    SubmittedAnswer,
                    (SubmittedAnswer.attempt_question_id == AttemptQuestion.id)
                    & (SubmittedAnswer.attempt_id == attempt.id),
                )
                .where(AttemptQuestion.attempt_id == attempt.id)
                .group_by(AttemptQuestion.coverage_key)
            )
        ).all()
    )
    section_breakdown = {
        key: {"total_count": total, "correct_count": correct}
        for key, total, correct in breakdown_rows
    }
    score_basis_points = correct_count * 500
    pass_status = final_exam_pass_status(correct_count)
    already_certified = (
        await _certification(
            db,
            employee_profile_id=employee_profile_id,
            training_id=attempt.training_id,
        )
        is not None
    )
    result = AttemptResult(
        attempt_id=attempt.id,
        correct_count=correct_count,
        total_count=20,
        score_basis_points=score_basis_points,
        knowledge_level=knowledge_level(score_basis_points),
        pass_status=pass_status,
        critical_error_count=critical_error_count,
        section_breakdown=section_breakdown,
        completed_at=now,
    )
    db.add(result)
    attempt.status = "completed"
    attempt.completed_at = now
    attempt.last_activity_at = now
    lease.last_seen_at = now
    await db.flush()
    newly_certified = pass_status == "passed" and not already_certified
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_attempt_finish",
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
            action="final_exam_attempt_completed",
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values={"status": "in_progress"},
            new_values={
                "status": "completed",
                "correct_count": correct_count,
                "pass_status": pass_status,
                "critical_error_count": critical_error_count,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    if newly_certified:
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="final_exam_certification_earned",
                target_type="attempt_result",
                target_id=result.id,
                old_values=None,
                new_values={"training_id": str(attempt.training_id)},
                request_id=request_id,
                outcome="success",
            )
        )
    await db.commit()
    return await _finish_response(
        db,
        attempt=attempt,
        result=result,
        newly_certified=newly_certified,
        replayed=False,
    )


async def finish_final_exam_attempt(
    db: AsyncSession,
    **kwargs: object,
) -> FinalExamFinishResponse:
    try:
        return await _finish_final_exam_attempt(db, **kwargs)  # type: ignore[arg-type]
    except Exception:
        await db.rollback()
        raise
