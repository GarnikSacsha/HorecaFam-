from datetime import datetime
from typing import cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentVersion,
    AttemptQuestion,
    AttemptResult,
    AttentionCase,
    AttentionCaseAction,
    AttentionCaseSource,
    CriticalError,
    MenuItemVersion,
    MenuItemVersionAllergen,
    SubmittedAnswer,
)

ATTENTION_ACTION_NAMESPACE = UUID("ab3e8fbb-4586-42f6-bbc0-ef3b9039d715")


def _deterministic_id(*parts: object) -> UUID:
    return uuid5(ATTENTION_ACTION_NAMESPACE, ":".join(str(part) for part in parts))


def _allergen_source_ids(question: AttemptQuestion) -> list[UUID]:
    sources = question.provenance_snapshot.get("sources")
    if not isinstance(sources, list):
        return []
    source_ids: set[UUID] = set()
    for source in sources:
        if not isinstance(source, dict) or source.get("role") != "correct_fact":
            continue
        raw_id = source.get("menu_item_version_allergen_id")
        if not isinstance(raw_id, str):
            continue
        try:
            source_ids.add(UUID(raw_id))
        except ValueError:
            continue
    return sorted(source_ids, key=str)


async def _assessment_type(
    db: AsyncSession,
    attempt: AssessmentAttempt,
) -> str | None:
    return cast(
        str | None,
        await db.scalar(
            select(Assessment.assessment_type)
            .join(AssessmentVersion, AssessmentVersion.assessment_id == Assessment.id)
            .where(AssessmentVersion.id == attempt.assessment_version_id)
        ),
    )


async def _critical_subject(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    question: AttemptQuestion,
) -> tuple[MenuItemVersion, MenuItemVersionAllergen] | None:
    source_ids = _allergen_source_ids(question)
    if not source_ids:
        return None
    row = (
        await db.execute(
            select(MenuItemVersion, MenuItemVersionAllergen)
            .join(
                MenuItemVersionAllergen,
                MenuItemVersionAllergen.menu_item_version_id == MenuItemVersion.id,
            )
            .where(
                MenuItemVersionAllergen.id.in_(source_ids),
                MenuItemVersionAllergen.organization_id == attempt.organization_id,
                MenuItemVersionAllergen.location_id == attempt.location_id,
                MenuItemVersion.organization_id == attempt.organization_id,
                MenuItemVersion.location_id == attempt.location_id,
            )
            .order_by(MenuItemVersionAllergen.id)
            .limit(1)
        )
    ).first()
    return None if row is None else row._tuple()


async def _record_case_action(
    db: AsyncSession,
    *,
    case: AttentionCase,
    action: str,
    occurred_at: datetime,
    source_id: UUID | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
) -> None:
    action_id = _deterministic_id(case.id, action, source_id or occurred_at.isoformat())
    await db.execute(
        postgresql_insert(AttentionCaseAction)
        .values(
            id=action_id,
            organization_id=case.organization_id,
            location_id=case.location_id,
            attention_case_id=case.id,
            actor_type="system",
            actor_user_id=None,
            action=action,
            from_state=from_state,
            to_state=to_state,
            comment=None,
            details=({"critical_error_id": str(source_id)} if source_id is not None else {}),
            created_at=occurred_at,
        )
        .on_conflict_do_nothing(index_elements=[AttentionCaseAction.id])
    )


async def _open_or_get_critical_case(
    db: AsyncSession,
    *,
    error: CriticalError,
) -> tuple[AttentionCase, bool]:
    case_id = uuid4()
    inserted_id = await db.scalar(
        postgresql_insert(AttentionCase)
        .values(
            id=case_id,
            organization_id=error.organization_id,
            location_id=error.location_id,
            training_id=error.training_id,
            employee_profile_id=error.employee_profile_id,
            case_type="critical_allergen",
            subject_key=error.subject_key,
            state="open",
            revision=0,
            created_at=error.occurred_at,
            updated_at=error.occurred_at,
        )
        .on_conflict_do_nothing()
        .returning(AttentionCase.id)
    )
    if inserted_id is not None:
        case = await db.get(AttentionCase, inserted_id)
        if case is None:
            raise RuntimeError("Inserted Attention Case is unavailable")
        await _record_case_action(
            db,
            case=case,
            action="opened",
            occurred_at=error.occurred_at,
            from_state=None,
            to_state="open",
        )
        return case, True

    case = await db.scalar(
        select(AttentionCase)
        .where(
            AttentionCase.organization_id == error.organization_id,
            AttentionCase.employee_profile_id == error.employee_profile_id,
            AttentionCase.training_id == error.training_id,
            AttentionCase.case_type == "critical_allergen",
            AttentionCase.subject_key == error.subject_key,
            AttentionCase.state.in_(("open", "acknowledged")),
        )
        .order_by(AttentionCase.created_at, AttentionCase.id)
        .with_for_update()
    )
    if case is None:
        raise RuntimeError("Concurrent Attention Case projection is unavailable")
    return case, False


async def _link_error_to_case(
    db: AsyncSession,
    *,
    error: CriticalError,
) -> None:
    existing = await db.scalar(
        select(AttentionCaseSource).where(AttentionCaseSource.critical_error_id == error.id)
    )
    if existing is not None:
        return
    case, _ = await _open_or_get_critical_case(db, error=error)
    source_id = _deterministic_id("critical-source", error.id)
    inserted_id = await db.scalar(
        postgresql_insert(AttentionCaseSource)
        .values(
            id=source_id,
            organization_id=error.organization_id,
            location_id=error.location_id,
            attention_case_id=case.id,
            critical_error_id=error.id,
            retake_requirement_id=None,
            created_at=error.occurred_at,
        )
        .on_conflict_do_nothing()
        .returning(AttentionCaseSource.id)
    )
    if inserted_id is not None:
        await _record_case_action(
            db,
            case=case,
            action="source_added",
            occurred_at=error.occurred_at,
            source_id=error.id,
        )


async def _project_answer(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    question: AttemptQuestion,
    answer: SubmittedAnswer,
    assessment_type: str,
) -> CriticalError | None:
    existing = await db.scalar(
        select(CriticalError).where(CriticalError.submitted_answer_id == answer.id)
    )
    if existing is not None:
        await _link_error_to_case(db, error=existing)
        return existing
    subject = await _critical_subject(db, attempt=attempt, question=question)
    if subject is None:
        return None
    item_version, allergen = subject
    subject_key = f"menu_item:{item_version.menu_item_id}:allergen:{allergen.allergen_id}"
    error_id = uuid4()
    inserted_id = await db.scalar(
        postgresql_insert(CriticalError)
        .values(
            id=error_id,
            organization_id=attempt.organization_id,
            location_id=attempt.location_id,
            training_id=attempt.training_id,
            employee_profile_id=attempt.employee_profile_id,
            assignment_id=attempt.assignment_id,
            attempt_id=attempt.id,
            attempt_question_id=question.id,
            submitted_answer_id=answer.id,
            menu_id=item_version.menu_id,
            menu_item_id=item_version.menu_item_id,
            allergen_id=allergen.allergen_id,
            critical_type="allergen",
            subject_key=subject_key,
            safe_context={
                "assessment_type": assessment_type,
                "attempt_question_position": question.position,
            },
            occurred_at=answer.submitted_at,
            created_at=answer.submitted_at,
        )
        .on_conflict_do_nothing()
        .returning(CriticalError.id)
    )
    projected = await db.get(CriticalError, inserted_id or error_id)
    if projected is None:
        projected = await db.scalar(
            select(CriticalError).where(CriticalError.submitted_answer_id == answer.id)
        )
    if projected is None:
        raise RuntimeError("Concurrent Critical Error projection is unavailable")
    await _link_error_to_case(db, error=projected)
    return projected


async def project_critical_errors_for_attempt(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
) -> list[CriticalError]:
    """Проєктує лише підтверджені critical Answers завершеної Practice/Final спроби."""

    if attempt.status != "completed" or attempt.question_count not in {10, 20}:
        return []
    assessment_type = await _assessment_type(db, attempt)
    if assessment_type not in {"whole_menu_knowledge_check", "menu_final_exam"}:
        return []
    rows = list(
        (
            await db.execute(
                select(AttemptQuestion, SubmittedAnswer)
                .join(
                    SubmittedAnswer,
                    (SubmittedAnswer.attempt_question_id == AttemptQuestion.id)
                    & (SubmittedAnswer.attempt_id == attempt.id),
                )
                .where(
                    AttemptQuestion.attempt_id == attempt.id,
                    AttemptQuestion.is_critical.is_(True),
                    SubmittedAnswer.is_correct.is_(False),
                    SubmittedAnswer.is_critical_error.is_(True),
                )
                .order_by(AttemptQuestion.position, SubmittedAnswer.id)
            )
        ).all()
    )
    projected: list[CriticalError] = []
    for question, answer in rows:
        error = await _project_answer(
            db,
            attempt=attempt,
            question=question,
            answer=answer,
            assessment_type=assessment_type,
        )
        if error is not None:
            projected.append(error)
    await db.flush()
    return projected


async def acknowledge_attention_case(
    db: AsyncSession,
    *,
    organization_id: UUID,
    case_id: UUID,
    actor_user_id: UUID,
    now: datetime,
) -> bool:
    """Переводить відкритий Case у follow-up без неявного завершення."""

    case = await db.scalar(
        select(AttentionCase)
        .where(
            AttentionCase.id == case_id,
            AttentionCase.organization_id == organization_id,
        )
        .with_for_update()
    )
    if case is None:
        raise ValueError("Attention Case is unavailable")
    if case.state == "resolved":
        raise ValueError("Resolved Attention Case cannot be acknowledged")
    if case.state == "acknowledged":
        return False
    case.state = "acknowledged"
    case.acknowledged_by_user_id = actor_user_id
    case.acknowledged_at = now
    case.revision += 1
    db.add(
        AttentionCaseAction(
            organization_id=case.organization_id,
            location_id=case.location_id,
            attention_case_id=case.id,
            actor_type="user",
            actor_user_id=actor_user_id,
            action="acknowledged",
            from_state="open",
            to_state="acknowledged",
            details={},
            created_at=now,
        )
    )
    await db.flush()
    return True


async def _clean_retake_is_proven(
    db: AsyncSession,
    *,
    case: AttentionCase,
    evidence_attempt_id: UUID,
) -> bool:
    if case.case_type != "critical_allergen" or case.subject_key is None:
        return False
    latest_source_at = await db.scalar(
        select(CriticalError.occurred_at)
        .join(
            AttentionCaseSource,
            AttentionCaseSource.critical_error_id == CriticalError.id,
        )
        .where(AttentionCaseSource.attention_case_id == case.id)
        .order_by(CriticalError.occurred_at.desc(), CriticalError.id.desc())
        .limit(1)
    )
    attempt = await db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.id == evidence_attempt_id,
            AssessmentAttempt.organization_id == case.organization_id,
            AssessmentAttempt.location_id == case.location_id,
            AssessmentAttempt.training_id == case.training_id,
            AssessmentAttempt.employee_profile_id == case.employee_profile_id,
            AssessmentAttempt.status == "completed",
        )
    )
    if (
        attempt is None
        or attempt.completed_at is None
        or latest_source_at is None
        or attempt.completed_at <= latest_source_at
    ):
        return False
    result = await db.scalar(select(AttemptResult).where(AttemptResult.attempt_id == attempt.id))
    assessment_type = await _assessment_type(db, attempt)
    if result is None:
        return False
    if assessment_type == "menu_final_exam":
        threshold_met = result.pass_status == "passed"
    elif assessment_type == "whole_menu_knowledge_check":
        threshold_met = result.score_basis_points >= 4000
    else:
        return False
    if not threshold_met:
        return False
    rows = list(
        (
            await db.execute(
                select(AttemptQuestion, SubmittedAnswer)
                .join(
                    SubmittedAnswer,
                    (SubmittedAnswer.attempt_question_id == AttemptQuestion.id)
                    & (SubmittedAnswer.attempt_id == attempt.id),
                )
                .where(
                    AttemptQuestion.attempt_id == attempt.id,
                    SubmittedAnswer.is_correct.is_(True),
                )
                .order_by(AttemptQuestion.position, SubmittedAnswer.id)
            )
        ).all()
    )
    for question, _answer in rows:
        subject = await _critical_subject(db, attempt=attempt, question=question)
        if subject is None:
            continue
        item_version, allergen = subject
        subject_key = f"menu_item:{item_version.menu_item_id}:allergen:{allergen.allergen_id}"
        if subject_key == case.subject_key:
            return True
    return False


async def correct_subject_keys_for_attempt(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
) -> set[str]:
    """Повертає лише стабільні critical subjects, які справді були перевірені правильно."""

    rows = list(
        (
            await db.execute(
                select(AttemptQuestion, SubmittedAnswer)
                .join(
                    SubmittedAnswer,
                    (SubmittedAnswer.attempt_question_id == AttemptQuestion.id)
                    & (SubmittedAnswer.attempt_id == attempt.id),
                )
                .where(
                    AttemptQuestion.attempt_id == attempt.id,
                    SubmittedAnswer.is_correct.is_(True),
                )
            )
        ).all()
    )
    subjects: set[str] = set()
    for question, _answer in rows:
        subject = await _critical_subject(db, attempt=attempt, question=question)
        if subject is None:
            continue
        item_version, allergen = subject
        subjects.add(f"menu_item:{item_version.menu_item_id}:allergen:{allergen.allergen_id}")
    return subjects


async def resolve_attention_case(
    db: AsyncSession,
    *,
    organization_id: UUID,
    case_id: UUID,
    actor_user_id: UUID,
    resolution_type: str,
    now: datetime,
    comment: str | None = None,
    evidence_attempt_id: UUID | None = None,
) -> bool:
    """Завершує Case лише явною дією та перевіреним типом доказу."""

    case = await db.scalar(
        select(AttentionCase)
        .where(
            AttentionCase.id == case_id,
            AttentionCase.organization_id == organization_id,
        )
        .with_for_update()
    )
    if case is None:
        raise ValueError("Attention Case is unavailable")
    if case.state == "resolved":
        return False
    normalized_comment = comment.strip() if comment is not None else None
    if resolution_type == "admin_follow_up":
        if normalized_comment is None or not 1 <= len(normalized_comment) <= 500:
            raise ValueError("Admin follow-up resolution requires a meaningful comment")
    elif resolution_type == "clean_retake":
        if evidence_attempt_id is None or not await _clean_retake_is_proven(
            db,
            case=case,
            evidence_attempt_id=evidence_attempt_id,
        ):
            raise ValueError("Clean retake evidence is not proven")
    else:
        raise ValueError("Unsupported critical Attention resolution")
    from_state = case.state
    case.state = "resolved"
    case.resolution_type = resolution_type
    case.resolution_actor_type = "user"
    case.resolved_by_user_id = actor_user_id
    case.resolved_at = now
    case.resolution_comment = normalized_comment
    case.revision += 1
    db.add(
        AttentionCaseAction(
            organization_id=case.organization_id,
            location_id=case.location_id,
            attention_case_id=case.id,
            actor_type="user",
            actor_user_id=actor_user_id,
            action="resolved",
            from_state=from_state,
            to_state="resolved",
            comment=normalized_comment,
            details=(
                {"evidence_attempt_id": str(evidence_attempt_id)}
                if evidence_attempt_id is not None
                else {}
            ),
            created_at=now,
        )
    )
    await db.flush()
    return True
