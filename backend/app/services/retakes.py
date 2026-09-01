import hashlib
from datetime import datetime, timedelta
from typing import Literal, cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentVersion,
    AttemptResult,
    AttentionCase,
    AttentionCaseAction,
    AttentionCaseSource,
    RetakeRequirement,
    RetakeRequirementAction,
)
from app.services.attention import correct_subject_keys_for_attempt

RETAKE_ACTION_NAMESPACE = UUID("01c5b328-687d-4f37-8da0-d751012e1383")

RetakeTimingState = Literal["scheduled", "approaching", "overdue", "frozen"]


def _action_id(*parts: object) -> UUID:
    return uuid5(RETAKE_ACTION_NAMESPACE, ":".join(str(part) for part in parts))


def _advisory_key(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big", signed=True)


async def _lock_deadline_projection(db: AsyncSession, requirement_id: UUID) -> None:
    await db.execute(
        select(func.pg_advisory_xact_lock(_advisory_key(f"retake-deadline:{requirement_id}")))
    )


async def _record_system_action(
    db: AsyncSession,
    *,
    requirement: RetakeRequirement,
    action: str,
    occurred_at: datetime,
    attempt_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    statement = (
        postgresql_insert(RetakeRequirementAction)
        .values(
            id=_action_id(requirement.id, action, attempt_id or occurred_at.isoformat()),
            organization_id=requirement.organization_id,
            location_id=requirement.location_id,
            retake_requirement_id=requirement.id,
            actor_type="system",
            actor_user_id=None,
            action=action,
            attempt_id=attempt_id,
            comment=None,
            details=details or {},
            created_at=occurred_at,
        )
        .on_conflict_do_nothing(index_elements=[RetakeRequirementAction.id])
    )
    await db.execute(statement)


async def _target_assessment_id(
    db: AsyncSession,
    attempt: AssessmentAttempt,
) -> UUID:
    assessment_id = await db.scalar(
        select(AssessmentVersion.assessment_id).where(
            AssessmentVersion.id == attempt.assessment_version_id
        )
    )
    if assessment_id is None:
        raise RuntimeError("Final Exam attempt has no stable target Assessment")
    return assessment_id


async def _current_failed_requirement(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    target_assessment_id: UUID,
) -> RetakeRequirement | None:
    return cast(
        RetakeRequirement | None,
        await db.scalar(
            select(RetakeRequirement)
            .where(
                RetakeRequirement.employee_profile_id == attempt.employee_profile_id,
                RetakeRequirement.training_id == attempt.training_id,
                RetakeRequirement.target_assessment_id == target_assessment_id,
                RetakeRequirement.reason == "failed_exam",
                RetakeRequirement.state == "active",
            )
            .order_by(RetakeRequirement.confirmed_at, RetakeRequirement.id)
            .with_for_update()
        ),
    )


async def _project_failed_result(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
    target_assessment_id: UUID,
) -> RetakeRequirement:
    source_requirement = await db.scalar(
        select(RetakeRequirement)
        .where(
            RetakeRequirement.reason == "failed_exam",
            RetakeRequirement.source_result_id == result.id,
        )
        .with_for_update()
    )
    if source_requirement is not None:
        return source_requirement

    requirement_id = uuid4()
    statement = (
        postgresql_insert(RetakeRequirement)
        .values(
            id=requirement_id,
            organization_id=attempt.organization_id,
            location_id=attempt.location_id,
            training_id=attempt.training_id,
            employee_profile_id=attempt.employee_profile_id,
            assignment_id=attempt.assignment_id,
            target_assessment_id=target_assessment_id,
            reason="failed_exam",
            state="active",
            source_result_id=result.id,
            source_attempt_id=attempt.id,
            source_attention_case_id=None,
            management_source_key=None,
            target_policy={
                "assessment_type": "menu_final_exam",
                "minimum_result": "passed",
            },
            proposed_at=None,
            proposed_by_user_id=None,
            confirmed_at=result.completed_at,
            confirmed_by_user_id=None,
            due_at=result.completed_at + timedelta(days=7),
            clock_frozen_at=None,
            frozen_seconds=0,
            completed_at=None,
            completion_attempt_id=None,
            cancelled_at=None,
            cancelled_by_user_id=None,
            cancellation_comment=None,
            revision=0,
            created_at=result.completed_at,
            updated_at=result.completed_at,
        )
        .on_conflict_do_nothing()
        .returning(RetakeRequirement.id)
    )
    inserted_id = await db.scalar(statement)
    if inserted_id is not None:
        requirement = await db.get(RetakeRequirement, inserted_id)
        if requirement is None:
            raise RuntimeError("Inserted Retake Requirement is unavailable")
        await _record_system_action(
            db,
            requirement=requirement,
            action="confirmed",
            occurred_at=result.completed_at,
            attempt_id=attempt.id,
        )
    else:
        requirement = await db.scalar(
            select(RetakeRequirement)
            .where(
                (
                    (RetakeRequirement.reason == "failed_exam")
                    & (RetakeRequirement.source_result_id == result.id)
                )
                | (
                    (RetakeRequirement.employee_profile_id == attempt.employee_profile_id)
                    & (RetakeRequirement.training_id == attempt.training_id)
                    & (RetakeRequirement.target_assessment_id == target_assessment_id)
                    & (RetakeRequirement.reason == "failed_exam")
                    & (RetakeRequirement.state == "active")
                )
            )
            .order_by(RetakeRequirement.confirmed_at, RetakeRequirement.id)
            .with_for_update()
        )
        if requirement is None:
            raise RuntimeError("Concurrent Retake Requirement projection is unavailable")

    if requirement.confirmed_at is None:
        raise RuntimeError("Active failed-exam Requirement has no confirmation timestamp")
    if result.completed_at < requirement.confirmed_at:
        requirement.assignment_id = attempt.assignment_id
        requirement.source_result_id = result.id
        requirement.source_attempt_id = attempt.id
        requirement.confirmed_at = result.completed_at
        requirement.due_at = result.completed_at + timedelta(days=7)
        requirement.revision += 1
        await _record_system_action(
            db,
            requirement=requirement,
            action="confirmed",
            occurred_at=result.completed_at,
            attempt_id=attempt.id,
            details={"earliest_source_correction": True},
        )

    await _record_system_action(
        db,
        requirement=requirement,
        action="attempt_observed",
        occurred_at=result.completed_at,
        attempt_id=attempt.id,
        details={"pass_status": "failed"},
    )
    return requirement


async def _project_passed_result(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
    target_assessment_id: UUID,
) -> RetakeRequirement | None:
    requirement = await _current_failed_requirement(
        db,
        attempt=attempt,
        target_assessment_id=target_assessment_id,
    )
    if requirement is None:
        return None
    if requirement.confirmed_at is None:
        raise RuntimeError("Active failed-exam Requirement has no confirmation timestamp")
    if result.completed_at < requirement.confirmed_at:
        return None

    await _record_system_action(
        db,
        requirement=requirement,
        action="attempt_observed",
        occurred_at=result.completed_at,
        attempt_id=attempt.id,
        details={"pass_status": "passed"},
    )
    requirement.state = "completed"
    requirement.completed_at = result.completed_at
    requirement.completion_attempt_id = attempt.id
    requirement.revision += 1
    await _record_system_action(
        db,
        requirement=requirement,
        action="completed",
        occurred_at=result.completed_at,
        attempt_id=attempt.id,
    )
    await _resolve_overdue_case(
        db,
        requirement=requirement,
        resolution_type="requirement_completed",
        occurred_at=result.completed_at,
    )
    await db.flush()
    return requirement


async def _record_system_case_action(
    db: AsyncSession,
    *,
    case: AttentionCase,
    requirement: RetakeRequirement,
    action: str,
    occurred_at: datetime,
    from_state: str | None,
    to_state: str | None,
) -> None:
    await db.execute(
        postgresql_insert(AttentionCaseAction)
        .values(
            id=_action_id("attention", case.id, action, requirement.id),
            organization_id=case.organization_id,
            location_id=case.location_id,
            attention_case_id=case.id,
            actor_type="system",
            actor_user_id=None,
            action=action,
            from_state=from_state,
            to_state=to_state,
            comment=None,
            details={"retake_requirement_id": str(requirement.id)},
            created_at=occurred_at,
        )
        .on_conflict_do_nothing(index_elements=[AttentionCaseAction.id])
    )


async def _resolve_overdue_case(
    db: AsyncSession,
    *,
    requirement: RetakeRequirement,
    resolution_type: Literal["requirement_completed", "requirement_cancelled"],
    occurred_at: datetime,
) -> bool:
    case = await db.scalar(
        select(AttentionCase)
        .join(
            AttentionCaseSource,
            AttentionCaseSource.attention_case_id == AttentionCase.id,
        )
        .where(
            AttentionCaseSource.retake_requirement_id == requirement.id,
            AttentionCase.case_type == "retake_overdue",
            AttentionCase.state.in_(("open", "acknowledged")),
        )
        .with_for_update()
    )
    if case is None:
        return False
    from_state = case.state
    case.state = "resolved"
    case.resolution_type = resolution_type
    case.resolution_actor_type = "system"
    case.resolved_by_user_id = None
    case.resolved_at = occurred_at
    case.resolution_comment = None
    case.revision += 1
    await _record_system_case_action(
        db,
        case=case,
        requirement=requirement,
        action="resolved",
        occurred_at=occurred_at,
        from_state=from_state,
        to_state="resolved",
    )
    return True


async def resolve_terminal_overdue_case(
    db: AsyncSession,
    *,
    requirement: RetakeRequirement,
    resolution_type: Literal["requirement_completed", "requirement_cancelled"],
    occurred_at: datetime,
) -> bool:
    """Завершує лише overdue-кейс, прямо пов'язаний із термінальною вимогою."""

    return await _resolve_overdue_case(
        db,
        requirement=requirement,
        resolution_type=resolution_type,
        occurred_at=occurred_at,
    )


async def _project_overdue_requirement(
    db: AsyncSession,
    *,
    requirement_id: UUID,
    now: datetime,
) -> AttentionCase | None:
    await _lock_deadline_projection(db, requirement_id)
    requirement = await db.scalar(
        select(RetakeRequirement)
        .where(RetakeRequirement.id == requirement_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        requirement is None
        or requirement.state != "active"
        or requirement.clock_frozen_at is not None
        or requirement.due_at > now
    ):
        return None
    existing_source = await db.scalar(
        select(AttentionCaseSource).where(
            AttentionCaseSource.retake_requirement_id == requirement.id
        )
    )
    if existing_source is not None:
        return None

    case = AttentionCase(
        organization_id=requirement.organization_id,
        location_id=requirement.location_id,
        training_id=requirement.training_id,
        employee_profile_id=requirement.employee_profile_id,
        case_type="retake_overdue",
        subject_key=None,
        state="open",
        revision=0,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    await db.flush()
    source = AttentionCaseSource(
        id=_action_id("deadline-source", requirement.id),
        organization_id=requirement.organization_id,
        location_id=requirement.location_id,
        attention_case_id=case.id,
        critical_error_id=None,
        retake_requirement_id=requirement.id,
        created_at=now,
    )
    db.add(source)
    await _record_system_case_action(
        db,
        case=case,
        requirement=requirement,
        action="opened",
        occurred_at=now,
        from_state=None,
        to_state="open",
    )
    await _record_system_case_action(
        db,
        case=case,
        requirement=requirement,
        action="source_added",
        occurred_at=now,
        from_state=None,
        to_state=None,
    )
    await _record_system_action(
        db,
        requirement=requirement,
        action="deadline_projected",
        occurred_at=now,
        details={"attention_case_id": str(case.id), "due_at": requirement.due_at.isoformat()},
    )
    await db.flush()
    return case


async def project_retake_deadlines(
    db: AsyncSession,
    *,
    now: datetime,
) -> list[AttentionCase]:
    """Проєктує прострочені активні вимоги в Attention без побічних зовнішніх дій."""

    if now.tzinfo is None:
        raise ValueError("Deadline projection requires a timezone-aware timestamp")
    requirement_ids = list(
        await db.scalars(
            select(RetakeRequirement.id)
            .where(
                RetakeRequirement.state == "active",
                RetakeRequirement.clock_frozen_at.is_(None),
                RetakeRequirement.due_at <= now,
            )
            .order_by(RetakeRequirement.due_at, RetakeRequirement.id)
        )
    )
    projected: list[AttentionCase] = []
    for requirement_id in requirement_ids:
        case = await _project_overdue_requirement(
            db,
            requirement_id=requirement_id,
            now=now,
        )
        if case is not None:
            projected.append(case)
    return projected


async def project_final_exam_follow_up(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
) -> RetakeRequirement | None:
    """Проєктує незмінний Result у поточне зобов'язання без зміни оцінки."""

    if attempt.status != "completed" or result.attempt_id != attempt.id:
        raise ValueError("Only the matching completed Final Exam result can be projected")
    if result.pass_status not in {"passed", "failed"} or result.total_count != 20:
        raise ValueError("Only a completed Final Exam pass/fail result can be projected")

    target_assessment_id = await _target_assessment_id(db, attempt)
    if result.pass_status == "failed":
        projected: RetakeRequirement | None = await _project_failed_result(
            db,
            attempt=attempt,
            result=result,
            target_assessment_id=target_assessment_id,
        )
    else:
        projected = await _project_passed_result(
            db,
            attempt=attempt,
            result=result,
            target_assessment_id=target_assessment_id,
        )
    await db.flush()
    return projected


async def project_managed_requirement_completion(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
) -> list[RetakeRequirement]:
    """Завершує лише активні Admin-вимоги, політика яких доведена цією спробою."""

    if attempt.status != "completed" or result.attempt_id != attempt.id:
        return []
    assessment_row = (
        await db.execute(
            select(Assessment.id, Assessment.assessment_type)
            .join(AssessmentVersion, AssessmentVersion.assessment_id == Assessment.id)
            .where(AssessmentVersion.id == attempt.assessment_version_id)
        )
    ).one_or_none()
    if assessment_row is None:
        return []
    target_assessment_id, assessment_type = assessment_row
    requirements = list(
        await db.scalars(
            select(RetakeRequirement)
            .where(
                RetakeRequirement.organization_id == attempt.organization_id,
                RetakeRequirement.location_id == attempt.location_id,
                RetakeRequirement.training_id == attempt.training_id,
                RetakeRequirement.employee_profile_id == attempt.employee_profile_id,
                RetakeRequirement.target_assessment_id == target_assessment_id,
                RetakeRequirement.reason.in_(("critical_error", "management_follow_up")),
                RetakeRequirement.state == "active",
            )
            .order_by(RetakeRequirement.confirmed_at, RetakeRequirement.id)
            .with_for_update()
        )
    )
    if not requirements:
        return []
    correct_subjects = await correct_subject_keys_for_attempt(db, attempt=attempt)
    completed: list[RetakeRequirement] = []
    for requirement in requirements:
        policy = requirement.target_policy
        policy_assessment_type = policy.get("assessment_type")
        if policy_assessment_type != assessment_type:
            continue
        minimum_result = policy.get("minimum_result")
        minimum_score = policy.get("minimum_score_basis_points")
        threshold_met = (
            result.pass_status == "passed"
            if minimum_result == "passed"
            else isinstance(minimum_score, int)
            and not isinstance(minimum_score, bool)
            and result.score_basis_points >= minimum_score
        )
        if not threshold_met:
            await _record_system_action(
                db,
                requirement=requirement,
                action="attempt_observed",
                occurred_at=result.completed_at,
                attempt_id=attempt.id,
                details={"policy_satisfied": False},
            )
            continue
        required_subjects = policy.get("required_subject_keys", [])
        if not isinstance(required_subjects, list) or any(
            not isinstance(subject, str) for subject in required_subjects
        ):
            continue
        required = set(cast(list[str], required_subjects))
        if requirement.reason == "critical_error":
            source_case = await db.get(AttentionCase, requirement.source_attention_case_id)
            if source_case is None or source_case.subject_key is None:
                continue
            required.add(source_case.subject_key)
        if not required.issubset(correct_subjects):
            await _record_system_action(
                db,
                requirement=requirement,
                action="attempt_observed",
                occurred_at=result.completed_at,
                attempt_id=attempt.id,
                details={"policy_satisfied": False},
            )
            continue
        await _record_system_action(
            db,
            requirement=requirement,
            action="attempt_observed",
            occurred_at=result.completed_at,
            attempt_id=attempt.id,
            details={"policy_satisfied": True},
        )
        requirement.state = "completed"
        requirement.completed_at = result.completed_at
        requirement.completion_attempt_id = attempt.id
        requirement.revision += 1
        await _record_system_action(
            db,
            requirement=requirement,
            action="completed",
            occurred_at=result.completed_at,
            attempt_id=attempt.id,
        )
        await _resolve_overdue_case(
            db,
            requirement=requirement,
            resolution_type="requirement_completed",
            occurred_at=result.completed_at,
        )
        completed.append(requirement)
    await db.flush()
    return completed


def retake_timing_state(
    requirement: RetakeRequirement,
    now: datetime,
) -> RetakeTimingState | None:
    """Обчислює правдивий timing state без окремого мінливого статусу."""

    if requirement.state != "active":
        return None
    if now.tzinfo is None or requirement.due_at.tzinfo is None:
        raise ValueError("Retake timing requires timezone-aware timestamps")
    if requirement.clock_frozen_at is not None:
        return "frozen"
    remaining = requirement.due_at - now
    if remaining <= timedelta(0):
        return "overdue"
    if remaining <= timedelta(hours=48):
        return "approaching"
    return "scheduled"


async def _locked_requirement(
    db: AsyncSession,
    requirement_id: UUID,
) -> RetakeRequirement:
    requirement = await db.scalar(
        select(RetakeRequirement)
        .where(RetakeRequirement.id == requirement_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if requirement is None:
        raise ValueError("Retake Requirement is unavailable")
    return requirement


async def freeze_retake_clock(
    db: AsyncSession,
    *,
    requirement: RetakeRequirement,
    now: datetime,
) -> bool:
    """Фіксує початок паузи один раз і не змінює первинне зобов'язання."""

    locked = await _locked_requirement(db, requirement.id)
    if locked.state != "active" or locked.clock_frozen_at is not None:
        return False
    locked.clock_frozen_at = now
    locked.revision += 1
    await _record_system_action(
        db,
        requirement=locked,
        action="frozen",
        occurred_at=now,
    )
    await db.flush()
    return True


async def resume_retake_clock(
    db: AsyncSession,
    *,
    requirement: RetakeRequirement,
    now: datetime,
) -> bool:
    """Повертає рівно заморожений час через зсув дедлайну."""

    locked = await _locked_requirement(db, requirement.id)
    frozen_at = locked.clock_frozen_at
    if locked.state != "active" or frozen_at is None:
        return False
    frozen_duration = now - frozen_at
    if frozen_duration < timedelta(0):
        raise ValueError("Resume time cannot precede freeze time")
    frozen_seconds = int(frozen_duration.total_seconds())
    locked.due_at += frozen_duration
    locked.frozen_seconds += frozen_seconds
    locked.clock_frozen_at = None
    locked.revision += 1
    await _record_system_action(
        db,
        requirement=locked,
        action="resumed",
        occurred_at=now,
        details={"frozen_seconds": frozen_seconds},
    )
    await db.flush()
    return True


async def freeze_employee_retake_clocks(
    db: AsyncSession,
    *,
    employee_profile_id: UUID,
    now: datetime,
) -> int:
    """Заморожує лише активні зобов'язання працівника без зміни їхньої історії."""

    requirements = list(
        await db.scalars(
            select(RetakeRequirement)
            .where(
                RetakeRequirement.employee_profile_id == employee_profile_id,
                RetakeRequirement.state == "active",
            )
            .order_by(RetakeRequirement.id)
            .with_for_update()
        )
    )
    changed = 0
    for requirement in requirements:
        changed += int(await freeze_retake_clock(db, requirement=requirement, now=now))
    return changed


async def resume_employee_retake_clocks(
    db: AsyncSession,
    *,
    employee_profile_id: UUID,
    now: datetime,
) -> int:
    """Повертає точний заморожений час активним зобов'язанням працівника."""

    requirements = list(
        await db.scalars(
            select(RetakeRequirement)
            .where(
                RetakeRequirement.employee_profile_id == employee_profile_id,
                RetakeRequirement.state == "active",
                RetakeRequirement.clock_frozen_at.is_not(None),
            )
            .order_by(RetakeRequirement.id)
            .with_for_update()
        )
    )
    changed = 0
    for requirement in requirements:
        changed += int(await resume_retake_clock(db, requirement=requirement, now=now))
    return changed
