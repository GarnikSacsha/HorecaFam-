from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AttemptResult,
    AuditEvent,
    LessonCompletion,
    LessonVersion,
    QuestionVersion,
    StandardRuleVersion,
    SubmittedAnswer,
    TrainingAssignment,
    TrainingModuleStandardDependency,
    TrainingModuleVersion,
)
from app.schemas.assessment import InteractiveAnswerPayload, PracticeAttemptOptionResponse
from app.schemas.course_assessment import (
    CourseAttemptResponse,
    CourseHistoryItem,
    CourseModuleSummary,
    CourseQuestion,
    CourseResult,
    CourseReview,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_answers import _grade_payload, _membership_state, knowledge_level
from app.services.interactive_attempts import (
    ATTEMPT_INACTIVITY,
    PoolCandidate,
    _previous_order,
    _require_active_training_participation,
    _snapshot_question,
    select_attempt_questions,
)
from app.services.module_audiences import module_visible_to


@dataclass(frozen=True)
class CourseActor:
    organization_id: UUID
    location_id: UUID
    employee_profile_id: UUID
    user_id: UUID
    session_id: UUID


def _error(code: str, message: str, status: int = 409) -> APIError:
    return APIError(status_code=status, code=code, message=message)


async def _owned(
    db: AsyncSession,
    actor: CourseActor,
    attempt_id: UUID,
    *,
    lock: bool = False,
) -> AssessmentAttempt:
    query = (
        select(AssessmentAttempt)
        .join(
            AssessmentVersion,
            AssessmentVersion.id == AssessmentAttempt.assessment_version_id,
        )
        .join(LessonVersion, LessonVersion.id == AssessmentVersion.lesson_version_id)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .where(
            AssessmentAttempt.id == attempt_id,
            AssessmentAttempt.organization_id == actor.organization_id,
            AssessmentAttempt.location_id == actor.location_id,
            AssessmentAttempt.employee_profile_id == actor.employee_profile_id,
            AssessmentAttempt.assessment_type == "course_knowledge_check",
            module_visible_to(actor.employee_profile_id),
        )
    )
    if lock:
        query = query.with_for_update(of=AssessmentAttempt)
    attempt = await db.scalar(query)
    if attempt is None:
        raise _error("RESOURCE_NOT_FOUND", "Ресурс не знайдено.", 404)
    return attempt


async def _response(
    db: AsyncSession,
    actor: CourseActor,
    attempt: AssessmentAttempt,
) -> CourseAttemptResponse:
    lease = await db.scalar(
        select(AttemptDeviceLease).where(AttemptDeviceLease.attempt_id == attempt.id)
    )
    if lease is None:
        raise RuntimeError("Course attempt device lease is unavailable")
    questions = list(
        await db.scalars(
            select(AttemptQuestion)
            .where(
                AttemptQuestion.attempt_id == attempt.id,
            )
            .order_by(AttemptQuestion.position)
        )
    )
    result = await db.scalar(select(AttemptResult).where(AttemptResult.attempt_id == attempt.id))
    finished = attempt.status == "completed" and result is not None
    membership = await _membership_state(db, actor.employee_profile_id)
    assignment = await db.get(TrainingAssignment, attempt.assignment_id)
    response_questions = []
    for question in questions:
        options = list(
            await db.scalars(
                select(AttemptOption)
                .where(
                    AttemptOption.attempt_question_id == question.id,
                )
                .order_by(AttemptOption.position)
            )
        )
        answer = await db.scalar(
            select(SubmittedAnswer).where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.attempt_question_id == question.id,
            )
        )
        response_questions.append(
            CourseQuestion(
                id=question.id,
                position=question.position,
                mechanic=question.mechanic,
                prompt_payload=question.prompt_payload,
                options=[
                    PracticeAttemptOptionResponse(
                        id=option.id, position=option.position, payload=option.payload
                    )
                    for option in options
                ],
                answer_payload=answer.answer_payload if answer else None,
                review=CourseReview(
                    is_correct=answer.is_correct,
                    correct_option_ids=[option.id for option in options if option.is_correct],
                    explanation_payload=question.explanation_payload,
                )
                if finished and answer
                else None,
            )
        )
    return CourseAttemptResponse(
        id=attempt.id,
        assessment_version_id=attempt.assessment_version_id,
        assignment_id=attempt.assignment_id,
        status=attempt.status,
        presentation_locale=attempt.presentation_locale,
        lease_generation=lease.generation,
        writable=(
            attempt.status == "in_progress"
            and lease.session_id == actor.session_id
            and membership == ("active", "active")
            and assignment is not None
            and assignment.status != "revoked"
        ),
        expires_at=attempt.expires_at,
        questions=response_questions,
        result=CourseResult(
            id=result.id,
            correct_count=result.correct_count,
            total_count=result.total_count,
            score_basis_points=result.score_basis_points,
            knowledge_level=result.knowledge_level,
            completed_at=result.completed_at,
        )
        if finished and result
        else None,
    )


async def get_course_attempt(
    db: AsyncSession, actor: CourseActor, attempt_id: UUID
) -> CourseAttemptResponse:
    return await _response(db, actor, await _owned(db, actor, attempt_id))


async def course_module_summary(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    module_version_id: UUID,
) -> CourseModuleSummary | None:
    version = await db.scalar(
        select(AssessmentVersion)
        .join(
            LessonVersion,
            LessonVersion.id == AssessmentVersion.lesson_version_id,
        )
        .where(
            LessonVersion.training_module_version_id == module_version_id,
            AssessmentVersion.assessment_type == "course_knowledge_check",
            AssessmentVersion.status == "published",
        )
        .order_by(AssessmentVersion.version_number.desc())
        .limit(1)
    )
    count = (
        version.question_count
        if version
        else await db.scalar(
            select(func.count(StandardRuleVersion.id))
            .join(
                TrainingModuleStandardDependency,
                TrainingModuleStandardDependency.standard_set_version_id
                == StandardRuleVersion.standard_set_version_id,
            )
            .where(TrainingModuleStandardDependency.training_module_version_id == module_version_id)
        )
    )
    if count is None or not 1 <= count <= 20:
        return None
    readiness = (
        await db.scalar(
            select(AssessmentReadiness).where(
                AssessmentReadiness.assessment_version_id == version.id,
            )
        )
        if version
        else None
    )
    ready = readiness is not None and readiness.status in {"ready", "warning"}
    missing = await db.scalar(
        select(LessonVersion.id)
        .where(
            LessonVersion.training_module_version_id == module_version_id,
            LessonVersion.required.is_(True),
            ~select(LessonCompletion.id)
            .where(
                LessonCompletion.assignment_id == assignment.id,
                LessonCompletion.lesson_version_id == LessonVersion.id,
            )
            .exists(),
        )
        .limit(1)
    )
    state = await _membership_state(db, assignment.employee_profile_id)
    rows = (
        (
            await db.execute(
                select(AssessmentAttempt, AttemptResult)
                .join(
                    AttemptResult,
                    AttemptResult.attempt_id == AssessmentAttempt.id,
                )
                .where(
                    AssessmentAttempt.assignment_id == assignment.id,
                    AssessmentAttempt.assessment_version_id == version.id,
                    AssessmentAttempt.status == "completed",
                )
                .order_by(AttemptResult.completed_at.desc())
                .limit(20)
            )
        ).all()
        if version
        else []
    )
    active = (
        await db.scalar(
            select(AssessmentAttempt.id).where(
                AssessmentAttempt.assignment_id == assignment.id,
                AssessmentAttempt.assessment_version_id == version.id,
                AssessmentAttempt.status == "in_progress",
            )
        )
        if version
        else None
    )
    return CourseModuleSummary(
        module_version_id=module_version_id,
        question_count=count,
        ready=ready,
        can_start=ready and missing is None and state == ("active", "active"),
        active_attempt_id=active,
        history=[
            CourseHistoryItem(
                attempt_id=attempt.id,
                result=CourseResult(
                    id=result.id,
                    correct_count=result.correct_count,
                    total_count=result.total_count,
                    score_basis_points=result.score_basis_points,
                    knowledge_level=result.knowledge_level,
                    completed_at=result.completed_at,
                ),
            )
            for attempt, result in rows
        ],
    )


async def _remember(
    db: AsyncSession,
    actor: CourseActor,
    *,
    action: str,
    key: str,
    fingerprint: str,
    attempt: AssessmentAttempt,
    request_id: UUID,
    now: datetime,
) -> None:
    await reserve_idempotency(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=actor.organization_id,
            actor_user_id=actor.user_id,
            actor_type="user",
            action=action,
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values=None,
            new_values={"status": attempt.status},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()


async def _replay(
    db: AsyncSession,
    actor: CourseActor,
    *,
    action: str,
    key: str,
    fingerprint: str,
    now: datetime,
) -> UUID | None:
    replay = await find_idempotency_replay(
        db,
        organization_id=actor.organization_id,
        actor_user_id=actor.user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        now=now,
    )
    return replay.resource_id if replay else None


async def start_course_attempt(
    db: AsyncSession,
    actor: CourseActor,
    module_version_id: UUID,
    *,
    locale: str,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> CourseAttemptResponse:
    await _require_active_training_participation(
        db,
        organization_id=actor.organization_id,
        location_id=actor.location_id,
        employee_profile_id=actor.employee_profile_id,
    )
    fingerprint = request_fingerprint(
        {"module_version_id": str(module_version_id), "locale": locale}
    )
    replay = await _replay(
        db,
        actor,
        action="course_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay:
        return await get_course_attempt(db, actor, replay)
    assignment = await db.scalar(
        select(TrainingAssignment)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.training_version_id == TrainingAssignment.training_version_id,
        )
        .where(
            TrainingAssignment.organization_id == actor.organization_id,
            TrainingAssignment.location_id == actor.location_id,
            TrainingAssignment.employee_profile_id == actor.employee_profile_id,
            TrainingAssignment.status != "revoked",
            TrainingModuleVersion.id == module_version_id,
            module_visible_to(actor.employee_profile_id),
        )
        .with_for_update(of=TrainingAssignment)
    )
    if assignment is None:
        raise _error("RESOURCE_NOT_FOUND", "Ресурс не знайдено.", 404)
    missing = await db.scalar(
        select(LessonVersion.id)
        .where(
            LessonVersion.training_module_version_id == module_version_id,
            LessonVersion.required.is_(True),
            ~select(LessonCompletion.id)
            .where(
                LessonCompletion.assignment_id == assignment.id,
                LessonCompletion.lesson_version_id == LessonVersion.id,
            )
            .exists(),
        )
        .limit(1)
    )
    if missing is not None:
        raise _error("COURSE_INCOMPLETE", "Спочатку завершіть обов’язкові уроки модуля.")
    version = await db.scalar(
        select(AssessmentVersion)
        .join(
            LessonVersion,
            LessonVersion.id == AssessmentVersion.lesson_version_id,
        )
        .join(
            AssessmentReadiness, AssessmentReadiness.assessment_version_id == AssessmentVersion.id
        )
        .where(
            AssessmentVersion.training_version_id == assignment.training_version_id,
            LessonVersion.training_module_version_id == module_version_id,
            AssessmentVersion.assessment_type == "course_knowledge_check",
            AssessmentVersion.status == "published",
            AssessmentReadiness.status.in_(["ready", "warning"]),
        )
        .order_by(AssessmentVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise _error("ASSESSMENT_NOT_READY", "Перевірка ще готується.")
    attempt = await db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.assignment_id == assignment.id,
            AssessmentAttempt.assessment_version_id == version.id,
            AssessmentAttempt.status == "in_progress",
        )
    )
    if attempt is not None and now >= attempt.expires_at:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
        await db.flush()
        attempt = None
    if attempt is None:
        rows = (
            await db.execute(
                select(AssessmentQuestionPool, QuestionVersion)
                .join(
                    QuestionVersion,
                    QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                )
                .where(
                    AssessmentQuestionPool.assessment_version_id == version.id,
                    AssessmentQuestionPool.eligible.is_(True),
                    QuestionVersion.status == "published",
                )
            )
        ).all()
        selected = select_attempt_questions(
            [
                PoolCandidate(
                    question_version_id=question.id,
                    coverage_key=pool.coverage_key,
                    mechanic=pool.mechanic,
                )
                for pool, question in rows
            ],
            previous_order=await _previous_order(
                db,
                employee_profile_id=actor.employee_profile_id,
                assessment_version_id=version.id,
            ),
            question_count=version.question_count,
        )
        if len(selected) != version.question_count:
            raise _error("ASSESSMENT_NOT_READY", "Перевірка ще готується.")
        attempt = AssessmentAttempt(
            organization_id=actor.organization_id,
            location_id=actor.location_id,
            training_id=assignment.training_id,
            employee_profile_id=actor.employee_profile_id,
            assignment_id=assignment.id,
            assessment_version_id=version.id,
            assessment_type="course_knowledge_check",
            status="in_progress",
            presentation_locale=locale,
            question_count=version.question_count,
            snapshot_schema_version=1,
            started_at=now,
            last_activity_at=now,
            expires_at=now + ATTEMPT_INACTIVITY,
        )
        db.add(attempt)
        await db.flush()
        by_id = {question.id: (pool, question) for pool, question in rows}
        for position, chosen in enumerate(selected):
            pool, question = by_id[chosen.question_version_id]
            await _snapshot_question(
                db, attempt=attempt, pool=pool, question_version=question, position=position
            )
        db.add(
            AttemptDeviceLease(
                attempt_id=attempt.id,
                session_id=actor.session_id,
                generation=1,
                acquired_at=now,
                last_seen_at=now,
            )
        )
    await _remember(
        db,
        actor,
        action="course_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        attempt=attempt,
        request_id=request_id,
        now=now,
    )
    return await _response(db, actor, attempt)


async def _writable(
    db: AsyncSession,
    actor: CourseActor,
    attempt: AssessmentAttempt,
    *,
    now: datetime,
    lease_generation: int | None,
) -> AttemptDeviceLease:
    state = await _membership_state(db, actor.employee_profile_id)
    assignment = await db.get(TrainingAssignment, attempt.assignment_id)
    if (
        state is None
        or state[0] != "active"
        or assignment is None
        or assignment.status == "revoked"
    ):
        raise _error("ATTEMPT_NOT_WRITABLE", "Спроба більше недоступна.")
    if state[1] == "paused":
        if attempt.status == "in_progress":
            attempt.last_activity_at = now
            attempt.expires_at = now + ATTEMPT_INACTIVITY
            await db.commit()
        raise _error("ATTEMPT_NOT_WRITABLE", "Спробу призупинено адміністратором.")
    if attempt.status == "completed":
        raise _error("ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    if attempt.status == "expired" or now >= attempt.expires_at:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
        await db.commit()
        raise _error("ATTEMPT_EXPIRED", "Строк активності спроби минув.")
    if attempt.status != "in_progress":
        raise _error("ATTEMPT_NOT_WRITABLE", "Спроба більше недоступна.")
    lease = await db.scalar(
        select(AttemptDeviceLease)
        .where(
            AttemptDeviceLease.attempt_id == attempt.id,
        )
        .with_for_update()
    )
    if lease is None:
        raise RuntimeError("Course attempt device lease is unavailable")
    if lease_generation is not None and (
        lease.session_id != actor.session_id or lease.generation != lease_generation
    ):
        raise _error("ATTEMPT_DEVICE_CONFLICT", "Інша сесія має право запису до цієї спроби.")
    return lease


async def save_course_answer(
    db: AsyncSession,
    actor: CourseActor,
    attempt_id: UUID,
    *,
    question_id: UUID,
    answer_payload: InteractiveAnswerPayload,
    lease_generation: int,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> CourseAttemptResponse:
    attempt = await _owned(db, actor, attempt_id, lock=True)
    payload = answer_payload.model_dump(mode="json")
    fingerprint = request_fingerprint(
        {"attempt_id": str(attempt_id), "question_id": str(question_id), "answer": payload}
    )
    if await _replay(
        db,
        actor,
        action="course_answer_save",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    ):
        return await _response(db, actor, attempt)
    lease = await _writable(db, actor, attempt, now=now, lease_generation=lease_generation)
    question = await db.scalar(
        select(AttemptQuestion).where(
            AttemptQuestion.id == question_id,
            AttemptQuestion.attempt_id == attempt_id,
        )
    )
    if question is None:
        raise _error("RESOURCE_NOT_FOUND", "Ресурс не знайдено.", 404)
    existing = await db.scalar(
        select(SubmittedAnswer.id).where(
            SubmittedAnswer.attempt_id == attempt_id,
            SubmittedAnswer.attempt_question_id == question_id,
        )
    )
    if existing is not None:
        raise _error("ANSWER_ALREADY_SUBMITTED", "Відповідь уже збережено.")
    options = list(
        await db.scalars(
            select(AttemptOption).where(AttemptOption.attempt_question_id == question_id)
        )
    )
    correct = _grade_payload(question, answer_payload, options)
    db.add(
        SubmittedAnswer(
            attempt_id=attempt_id,
            attempt_question_id=question_id,
            answer_payload=payload,
            is_correct=correct,
            is_critical_error=question.is_critical and not correct,
            idempotency_key=idempotency_key,
            submitted_at=now,
        )
    )
    attempt.last_activity_at = now
    attempt.expires_at = now + ATTEMPT_INACTIVITY
    lease.last_seen_at = now
    await _remember(
        db,
        actor,
        action="course_answer_save",
        key=idempotency_key,
        fingerprint=fingerprint,
        attempt=attempt,
        request_id=request_id,
        now=now,
    )
    return await _response(db, actor, attempt)


async def finish_course_attempt(
    db: AsyncSession,
    actor: CourseActor,
    attempt_id: UUID,
    *,
    lease_generation: int,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> CourseAttemptResponse:
    attempt = await _owned(db, actor, attempt_id, lock=True)
    fingerprint = request_fingerprint(
        {"attempt_id": str(attempt_id), "lease_generation": lease_generation}
    )
    if await _replay(
        db,
        actor,
        action="course_attempt_finish",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    ):
        return await _response(db, actor, attempt)
    lease = await _writable(db, actor, attempt, now=now, lease_generation=lease_generation)
    answers = list(
        await db.scalars(select(SubmittedAnswer).where(SubmittedAnswer.attempt_id == attempt.id))
    )
    if len(answers) != attempt.question_count:
        raise _error("COURSE_ANSWERS_INCOMPLETE", "Потрібно відповісти на всі запитання.")
    correct_count = sum(answer.is_correct for answer in answers)
    score = correct_count * 10000 // attempt.question_count
    db.add(
        AttemptResult(
            attempt_id=attempt.id,
            assessment_type="course_knowledge_check",
            correct_count=correct_count,
            total_count=attempt.question_count,
            score_basis_points=score,
            knowledge_level=knowledge_level(score),
            pass_status=None,
            critical_error_count=sum(answer.is_critical_error for answer in answers),
            section_breakdown={},
            completed_at=now,
        )
    )
    attempt.status = "completed"
    attempt.completed_at = now
    attempt.last_activity_at = now
    lease.last_seen_at = now
    await _remember(
        db,
        actor,
        action="course_attempt_finish",
        key=idempotency_key,
        fingerprint=fingerprint,
        attempt=attempt,
        request_id=request_id,
        now=now,
    )
    return await _response(db, actor, attempt)


async def takeover_course_attempt(
    db: AsyncSession,
    actor: CourseActor,
    attempt_id: UUID,
    *,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> CourseAttemptResponse:
    attempt = await _owned(db, actor, attempt_id, lock=True)
    fingerprint = request_fingerprint({"attempt_id": str(attempt_id)})
    if await _replay(
        db,
        actor,
        action="course_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    ):
        return await _response(db, actor, attempt)
    lease = await _writable(db, actor, attempt, now=now, lease_generation=None)
    lease.session_id = actor.session_id
    lease.generation += 1
    lease.acquired_at = now
    lease.last_seen_at = now
    attempt.last_activity_at = now
    attempt.expires_at = now + ATTEMPT_INACTIVITY
    await _remember(
        db,
        actor,
        action="course_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        attempt=attempt,
        request_id=request_id,
        now=now,
    )
    return await _response(db, actor, attempt)
