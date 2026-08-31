from datetime import datetime, timedelta
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
    AuditEvent,
    SubmittedAnswer,
    TrainingAssignment,
)
from app.schemas.assessment import (
    FinalExamAnswerResponse,
    FinalExamSavedAnswerResponse,
    InteractiveAnswerPayload,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_answers import _grade_payload, _membership_state, _payload_dict


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


async def _response(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    answer: SubmittedAnswer,
    replayed: bool,
) -> FinalExamAnswerResponse:
    answered_count = (
        await db.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(SubmittedAnswer.attempt_id == attempt.id)
        )
        or 0
    )
    next_question_id = await db.scalar(
        select(AttemptQuestion.id)
        .where(
            AttemptQuestion.attempt_id == attempt.id,
            ~AttemptQuestion.id.in_(
                select(SubmittedAnswer.attempt_question_id).where(
                    SubmittedAnswer.attempt_id == attempt.id
                )
            ),
        )
        .order_by(AttemptQuestion.position)
        .limit(1)
    )
    return FinalExamAnswerResponse(
        answer=FinalExamSavedAnswerResponse(
            id=answer.id,
            answer_payload=answer.answer_payload,
            submitted_at=answer.submitted_at,
        ),
        answered_count=answered_count,
        next_question_id=next_question_id,
        replayed=replayed,
    )


async def save_final_exam_answer(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    attempt_id: UUID,
    attempt_question_id: UUID,
    answer_payload: InteractiveAnswerPayload,
    lease_generation: int,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> FinalExamAnswerResponse:
    attempt = await db.scalar(
        select(AssessmentAttempt)
        .join(AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id)
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            AssessmentAttempt.id == attempt_id,
            AssessmentAttempt.organization_id == organization_id,
            AssessmentAttempt.location_id == location_id,
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            Assessment.assessment_type == "menu_final_exam",
        )
        .with_for_update(of=AssessmentAttempt)
    )
    if attempt is None:
        raise _not_found()
    question = await db.scalar(
        select(AttemptQuestion).where(
            AttemptQuestion.id == attempt_question_id,
            AttemptQuestion.attempt_id == attempt.id,
        )
    )
    if question is None:
        raise _not_found()
    payload_dict = _payload_dict(answer_payload)
    fingerprint = request_fingerprint(
        {
            "attempt_id": str(attempt.id),
            "attempt_question_id": str(question.id),
            "answer_payload": payload_dict,
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_answer_save",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        replay_answer = await db.get(SubmittedAnswer, replay.resource_id)
        if replay_answer is None or replay_answer.attempt_id != attempt.id:
            raise RuntimeError("Final Exam answer replay resource is unavailable")
        return await _response(db, attempt=attempt, answer=replay_answer, replayed=True)
    existing = await db.scalar(
        select(SubmittedAnswer).where(
            SubmittedAnswer.attempt_id == attempt.id,
            SubmittedAnswer.attempt_question_id == question.id,
        )
    )
    if existing is not None:
        raise _error(409, "ANSWER_ALREADY_SUBMITTED", "Відповідь уже збережено.")
    membership_state = await _membership_state(db, employee_profile_id)
    if membership_state is None or membership_state[0] != "active":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба зараз недоступна для запису.")
    if membership_state[1] == "paused":
        # Пауза не повинна витрачати вікно неактивності незавершеної спроби.
        attempt.last_activity_at = now
        attempt.expires_at = now + timedelta(days=7)
        await db.commit()
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спробу призупинено адміністратором.")
    assignment = await db.get(TrainingAssignment, attempt.assignment_id)
    if assignment is None or assignment.status != "completed":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба більше недоступна для запису.")
    if attempt.status == "completed":
        raise _error(409, "ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    if attempt.status == "expired" or now >= attempt.expires_at:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
        await db.commit()
        raise _error(409, "ATTEMPT_EXPIRED", "Строк активності спроби минув.")
    if attempt.status != "in_progress":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба більше недоступна для запису.")
    lease = await db.scalar(
        select(AttemptDeviceLease)
        .where(AttemptDeviceLease.attempt_id == attempt.id)
        .with_for_update()
    )
    if lease is None or lease.session_id != session_id or lease.generation != lease_generation:
        raise _error(
            409,
            "ATTEMPT_DEVICE_CONFLICT",
            "Інша сесія має право запису до цієї спроби.",
        )
    options = list(
        await db.scalars(
            select(AttemptOption).where(AttemptOption.attempt_question_id == question.id)
        )
    )
    is_correct = _grade_payload(question, answer_payload, options)
    answer = SubmittedAnswer(
        attempt_id=attempt.id,
        attempt_question_id=question.id,
        answer_payload=payload_dict,
        is_correct=is_correct,
        is_critical_error=question.is_critical and not is_correct,
        idempotency_key=idempotency_key,
        submitted_at=now,
    )
    db.add(answer)
    await db.flush()
    attempt.last_activity_at = now
    attempt.expires_at = now + timedelta(days=7)
    lease.last_seen_at = now
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_answer_save",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="submitted_answer",
        resource_id=answer.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="final_exam_answer_saved",
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values=None,
            new_values={"attempt_question_id": str(question.id)},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return await _response(db, attempt=attempt, answer=answer, replayed=False)
