from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AssessmentAttempt,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AttemptResult,
    AuditEvent,
    EmployeeProfile,
    OrganizationMembership,
    SubmittedAnswer,
    TrainingAssignment,
)
from app.schemas.assessment import (
    InteractiveAnswerPayload,
    InteractiveAnswerResponse,
    InteractiveConfirmedAnswerResponse,
    InteractiveFeedbackResponse,
    InteractiveResultResponse,
    MatchingSubmission,
    MultipleChoiceSubmission,
    OrderingSubmission,
    SingleChoiceSubmission,
)


def grade_selected_options(
    mechanic: str,
    selected_option_ids: set[UUID],
    correct_option_ids: set[UUID],
    allowed_option_ids: list[UUID],
) -> bool:
    allowed = set(allowed_option_ids)
    if not selected_option_ids or not selected_option_ids <= allowed:
        return False
    if mechanic == "single_choice" and len(selected_option_ids) != 1:
        return False
    return selected_option_ids == correct_option_ids


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _payload_dict(payload: InteractiveAnswerPayload) -> dict[str, object]:
    return payload.model_dump(mode="json")


async def _membership_state(
    db: AsyncSession,
    employee_profile_id: UUID,
) -> tuple[str, str] | None:
    membership = await db.scalar(
        select(OrganizationMembership)
        .join(
            EmployeeProfile,
            EmployeeProfile.membership_id == OrganizationMembership.id,
        )
        .where(EmployeeProfile.id == employee_profile_id)
    )
    if membership is None:
        return None
    return membership.status, membership.training_participation_status


async def _result_response(
    db: AsyncSession,
    attempt: AssessmentAttempt,
) -> InteractiveResultResponse | None:
    result = await db.scalar(select(AttemptResult).where(AttemptResult.attempt_id == attempt.id))
    if result is None or attempt.completed_at is None:
        return None
    return InteractiveResultResponse(
        id=result.id,
        correct_count=result.correct_count,
        score_basis_points=result.score_basis_points,
        knowledge_level=result.knowledge_level,
        completed_at=attempt.completed_at,
    )


async def _answer_response(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    question: AttemptQuestion,
    answer: SubmittedAnswer,
    replayed: bool,
) -> InteractiveAnswerResponse:
    options = list(
        await db.scalars(
            select(AttemptOption).where(AttemptOption.attempt_question_id == question.id)
        )
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
    confirmed = InteractiveConfirmedAnswerResponse(
        id=answer.id,
        answer_payload=answer.answer_payload,
        is_correct=answer.is_correct,
        submitted_at=answer.submitted_at,
    )
    feedback = InteractiveFeedbackResponse(
        is_correct=answer.is_correct,
        correct_option_ids=sorted((option.id for option in options if option.is_correct), key=str),
        explanation_payload=question.explanation_payload,
    )
    return InteractiveAnswerResponse(
        answer=confirmed,
        feedback=feedback,
        next_question_id=next_question_id,
        attempt_status=attempt.status,
        result=await _result_response(db, attempt),
        replayed=replayed,
    )


def _selected_ids(payload: InteractiveAnswerPayload) -> set[UUID]:
    if isinstance(payload, SingleChoiceSubmission):
        return {payload.option_id}
    if isinstance(payload, (MultipleChoiceSubmission, OrderingSubmission)):
        return set(payload.option_ids)
    if isinstance(payload, MatchingSubmission):
        return {
            option_id
            for pair in payload.pairs
            for option_id in (pair.left_option_id, pair.right_option_id)
        }
    raise AssertionError("Unsupported interactive answer payload")


def _grade_payload(
    question: AttemptQuestion,
    payload: InteractiveAnswerPayload,
    options: list[AttemptOption],
) -> bool:
    if payload.mechanic != question.mechanic:
        raise _error(422, "ANSWER_PAYLOAD_INVALID", "Формат відповіді не відповідає питанню.")
    allowed_ids = [option.id for option in options]
    selected = _selected_ids(payload)
    if not selected <= set(allowed_ids):
        raise _not_found()
    correct_ids = {option.id for option in options if option.is_correct}
    if isinstance(payload, OrderingSubmission):
        if len(payload.option_ids) != len(options):
            return False
        correct_keys = question.grading_payload.get("correct_option_keys")
        option_by_id = {option.id: option for option in options}
        submitted_keys = [
            option_by_id[option_id].payload.get("stable_key") for option_id in payload.option_ids
        ]
        return isinstance(correct_keys, list) and submitted_keys == correct_keys
    if isinstance(payload, MatchingSubmission):
        correct_pairs = question.grading_payload.get("correct_pairs")
        if not isinstance(correct_pairs, list):
            return False
        option_by_id = {option.id: option for option in options}
        submitted_pairs = [
            [
                option_by_id[pair.left_option_id].payload.get("stable_key"),
                option_by_id[pair.right_option_id].payload.get("stable_key"),
            ]
            for pair in payload.pairs
        ]
        return sorted(submitted_pairs) == sorted(correct_pairs)
    return grade_selected_options(question.mechanic, selected, correct_ids, allowed_ids)


def knowledge_level(score_basis_points: int) -> str:
    if score_basis_points < 4000:
        return "very_weak"
    if score_basis_points < 6000:
        return "weak"
    if score_basis_points < 8000:
        return "good"
    return "strong"


async def _complete_attempt(
    db: AsyncSession,
    attempt: AssessmentAttempt,
    *,
    now: datetime,
) -> AttemptResult:
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
    score_basis_points = correct_count * 2000
    result = AttemptResult(
        attempt_id=attempt.id,
        correct_count=correct_count,
        total_count=5,
        score_basis_points=score_basis_points,
        knowledge_level=knowledge_level(score_basis_points),
        pass_status=None,
        critical_error_count=0,
        section_breakdown={},
        completed_at=now,
    )
    db.add(result)
    attempt.status = "completed"
    attempt.completed_at = now
    attempt.last_activity_at = now
    await db.flush()
    return result


async def submit_interactive_answer(
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
) -> InteractiveAnswerResponse:
    attempt = await db.scalar(
        select(AssessmentAttempt)
        .where(
            AssessmentAttempt.id == attempt_id,
            AssessmentAttempt.organization_id == organization_id,
            AssessmentAttempt.location_id == location_id,
            AssessmentAttempt.employee_profile_id == employee_profile_id,
        )
        .with_for_update()
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
    replay = await db.scalar(
        select(SubmittedAnswer).where(
            SubmittedAnswer.attempt_id == attempt.id,
            SubmittedAnswer.idempotency_key == idempotency_key,
        )
    )
    if replay is not None:
        if replay.attempt_question_id != question.id or replay.answer_payload != payload_dict:
            raise _error(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Ключ ідемпотентності вже використано для іншої відповіді.",
            )
        return await _answer_response(
            db, attempt=attempt, question=question, answer=replay, replayed=True
        )
    existing = await db.scalar(
        select(SubmittedAnswer).where(
            SubmittedAnswer.attempt_id == attempt.id,
            SubmittedAnswer.attempt_question_id == question.id,
        )
    )
    if existing is not None:
        raise _error(409, "ANSWER_ALREADY_SUBMITTED", "Відповідь уже підтверджено.")
    membership_state = await _membership_state(db, employee_profile_id)
    if membership_state is None or membership_state[0] != "active":
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба зараз недоступна для запису.")
    if membership_state[1] == "paused":
        # Пауза не повинна витрачати вікно доступності незавершеної спроби.
        attempt.last_activity_at = now
        attempt.expires_at = now + timedelta(days=7)
        await db.commit()
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба призупинена адміністратором.")
    assignment = await db.get(TrainingAssignment, attempt.assignment_id)
    if assignment is None or not (
        assignment.status != "revoked"
        or (
            assignment.status == "revoked"
            and assignment.revoke_reason == "rollout"
            and assignment.source_rollout_id is not None
        )
    ):
        raise _error(409, "ATTEMPT_NOT_WRITABLE", "Спроба більше недоступна для запису.")
    if attempt.status == "completed":
        raise _error(409, "ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    if attempt.status == "expired" or now >= attempt.expires_at:
        attempt.status = "expired"
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
        is_critical_error=False,
        idempotency_key=idempotency_key,
        submitted_at=now,
    )
    db.add(answer)
    attempt.last_activity_at = now
    attempt.expires_at = now + timedelta(days=7)
    lease.last_seen_at = now
    await db.flush()
    answer_count = (
        await db.scalar(
            select(func.count())
            .select_from(SubmittedAnswer)
            .where(SubmittedAnswer.attempt_id == attempt.id)
        )
        or 0
    )
    if answer_count == 5:
        await _complete_attempt(db, attempt, now=now)
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="interactive_attempt_completed",
                target_type="assessment_attempt",
                target_id=attempt.id,
                old_values={"status": "in_progress"},
                new_values={"status": "completed"},
                request_id=request_id,
                outcome="success",
            )
        )
    await db.commit()
    return await _answer_response(
        db, attempt=attempt, question=question, answer=answer, replayed=False
    )
