import base64
import binascii
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AttentionCase,
    AttentionCaseSource,
    EmployeeProfile,
    RetakeRequirement,
    RetakeRequirementAction,
    TrainingAssignment,
)
from app.schemas.attention import (
    AttentionCaseCollection,
    AttentionCaseResponse,
    RetakeRequirementCollection,
    RetakeRequirementResponse,
)
from app.services.attention import acknowledge_attention_case, resolve_attention_case
from app.services.idempotency import request_fingerprint
from app.services.retakes import resolve_terminal_overdue_case, retake_timing_state


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _requirement_not_found() -> APIError:
    return _error(404, "RETAKE_REQUIREMENT_NOT_FOUND", "Вимогу перескладання не знайдено.")


def _attention_not_found() -> APIError:
    return _error(404, "ATTENTION_CASE_NOT_FOUND", "Кейс уваги не знайдено.")


def _invalid_cursor() -> APIError:
    return _error(422, "INVALID_CURSOR", "Некоректний курсор сторінки.")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None:
        raise _error(422, "RETAKE_DUE_AT_INVALID", "Дедлайн має містити часовий пояс.")


def _encode_cursor(filters: Mapping[str, object], key: list[object]) -> str:
    payload = json.dumps(
        {"f": request_fingerprint(dict(filters)), "k": key},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(
    cursor: str,
    filters: Mapping[str, object],
) -> list[object]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(f"{cursor}{padding}").decode())
        if (
            not isinstance(payload, dict)
            or payload.get("f") != request_fingerprint(dict(filters))
            or not isinstance(payload.get("k"), list)
        ):
            raise ValueError
        return cast(list[object], payload["k"])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _invalid_cursor() from exc


async def requirement_response(
    requirement: RetakeRequirement,
    *,
    now: datetime,
) -> RetakeRequirementResponse:
    return RetakeRequirementResponse(
        id=requirement.id,
        organization_id=requirement.organization_id,
        location_id=requirement.location_id,
        training_id=requirement.training_id,
        employee_profile_id=requirement.employee_profile_id,
        assignment_id=requirement.assignment_id,
        target_assessment_id=requirement.target_assessment_id,
        reason=requirement.reason,
        state=requirement.state,
        timing_state=retake_timing_state(requirement, now),
        source_result_id=requirement.source_result_id,
        source_attempt_id=requirement.source_attempt_id,
        source_attention_case_id=requirement.source_attention_case_id,
        management_source_key=requirement.management_source_key,
        target_policy=requirement.target_policy,
        proposed_at=requirement.proposed_at,
        confirmed_at=requirement.confirmed_at,
        due_at=requirement.due_at,
        clock_frozen_at=requirement.clock_frozen_at,
        completed_at=requirement.completed_at,
        completion_attempt_id=requirement.completion_attempt_id,
        cancelled_at=requirement.cancelled_at,
        cancellation_comment=requirement.cancellation_comment,
        revision=requirement.revision,
    )


async def attention_response(
    db: AsyncSession,
    case: AttentionCase,
) -> AttentionCaseResponse:
    sources = list(
        await db.scalars(
            select(AttentionCaseSource)
            .where(AttentionCaseSource.attention_case_id == case.id)
            .order_by(AttentionCaseSource.created_at, AttentionCaseSource.id)
        )
    )
    critical_ids = [source.critical_error_id for source in sources if source.critical_error_id]
    retake_id = next(
        (source.retake_requirement_id for source in sources if source.retake_requirement_id),
        None,
    )
    return AttentionCaseResponse(
        id=case.id,
        organization_id=case.organization_id,
        location_id=case.location_id,
        training_id=case.training_id,
        employee_profile_id=case.employee_profile_id,
        case_type=case.case_type,
        severity="critical" if case.case_type == "critical_allergen" else "overdue",
        subject_key=case.subject_key,
        state=case.state,
        revision=case.revision,
        acknowledged_at=case.acknowledged_at,
        resolution_type=case.resolution_type,
        resolved_at=case.resolved_at,
        resolution_comment=case.resolution_comment,
        critical_error_ids=critical_ids,
        retake_requirement_id=retake_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def get_requirement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    requirement_id: UUID,
) -> RetakeRequirement:
    requirement = await db.scalar(
        select(RetakeRequirement).where(
            RetakeRequirement.id == requirement_id,
            RetakeRequirement.organization_id == organization_id,
        )
    )
    if requirement is None:
        raise _requirement_not_found()
    return requirement


async def get_attention_case(
    db: AsyncSession,
    *,
    organization_id: UUID,
    attention_id: UUID,
) -> AttentionCase:
    case = await db.scalar(
        select(AttentionCase).where(
            AttentionCase.id == attention_id,
            AttentionCase.organization_id == organization_id,
        )
    )
    if case is None:
        raise _attention_not_found()
    return case


async def list_requirements(
    db: AsyncSession,
    *,
    organization_id: UUID,
    now: datetime,
    state: str | None,
    timing_state: str | None,
    reason: str | None,
    location_id: UUID | None,
    employee_query: str | None,
    cursor: str | None,
    limit: int,
) -> RetakeRequirementCollection:
    statement = select(RetakeRequirement).where(
        RetakeRequirement.organization_id == organization_id
    )
    if state is not None:
        statement = statement.where(RetakeRequirement.state == state)
    if reason is not None:
        statement = statement.where(RetakeRequirement.reason == reason)
    if location_id is not None:
        statement = statement.where(RetakeRequirement.location_id == location_id)
    if employee_query is not None:
        normalized = employee_query.strip()
        if not normalized:
            raise _error(422, "VALIDATION_ERROR", "Пошуковий запит не може бути порожнім.")
        pattern = f"%{normalized.replace('%', r'\%').replace('_', r'\_')}%"
        try:
            exact_employee_id = UUID(normalized)
        except ValueError:
            exact_employee_id = None
        statement = statement.join(
            EmployeeProfile, EmployeeProfile.id == RetakeRequirement.employee_profile_id
        ).where(
            or_(
                EmployeeProfile.id == exact_employee_id,
                EmployeeProfile.first_name.ilike(pattern, escape="\\"),
                EmployeeProfile.last_name.ilike(pattern, escape="\\"),
            )
        )
    rows = list(await db.scalars(statement))
    if timing_state is not None:
        rows = [item for item in rows if retake_timing_state(item, now) == timing_state]
    priority = {"overdue": 0, "approaching": 1, "scheduled": 2, "frozen": 3, None: 4}
    rows.sort(
        key=lambda item: (priority[retake_timing_state(item, now)], item.due_at, str(item.id))
    )
    filters = {
        "state": state,
        "timing_state": timing_state,
        "reason": reason,
        "location_id": str(location_id) if location_id else None,
        "employee_query": employee_query.strip() if employee_query else None,
    }
    start = 0
    if cursor is not None:
        key = _decode_cursor(cursor, filters)
        if len(key) != 3:
            raise _invalid_cursor()
        try:
            cursor_key = (
                int(str(key[0])),
                datetime.fromisoformat(str(key[1])),
                str(UUID(str(key[2]))),
            )
        except (TypeError, ValueError) as exc:
            raise _invalid_cursor() from exc
        start = next(
            (
                index
                for index, item in enumerate(rows)
                if (priority[retake_timing_state(item, now)], item.due_at, str(item.id))
                > cursor_key
            ),
            len(rows),
        )
    page = rows[start : start + limit + 1]
    visible = page[:limit]
    next_cursor = None
    if len(page) > limit and visible:
        last = visible[-1]
        next_cursor = _encode_cursor(
            filters,
            [priority[retake_timing_state(last, now)], last.due_at.isoformat(), str(last.id)],
        )
    return RetakeRequirementCollection(
        items=[await requirement_response(item, now=now) for item in visible],
        next_cursor=next_cursor,
    )


async def list_attention(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID | None,
    state: str | None,
    case_type: str | None,
    severity: str | None,
    location_id: UUID | None,
    employee_query: str | None,
    cursor: str | None,
    limit: int,
) -> AttentionCaseCollection:
    statement = select(AttentionCase).where(AttentionCase.organization_id == organization_id)
    if employee_profile_id is not None:
        exists = await db.scalar(
            select(EmployeeProfile.id).where(
                EmployeeProfile.id == employee_profile_id,
                EmployeeProfile.organization_id == organization_id,
            )
        )
        if exists is None:
            raise _attention_not_found()
        statement = statement.where(AttentionCase.employee_profile_id == employee_profile_id)
    if state is not None:
        statement = statement.where(AttentionCase.state == state)
    if case_type is not None:
        statement = statement.where(AttentionCase.case_type == case_type)
    if severity is not None:
        statement = statement.where(
            AttentionCase.case_type
            == ("critical_allergen" if severity == "critical" else "retake_overdue")
        )
    if location_id is not None:
        statement = statement.where(AttentionCase.location_id == location_id)
    if employee_query is not None:
        normalized = employee_query.strip()
        if not normalized:
            raise _error(422, "VALIDATION_ERROR", "Пошуковий запит не може бути порожнім.")
        pattern = f"%{normalized.replace('%', r'\%').replace('_', r'\_')}%"
        statement = statement.join(
            EmployeeProfile, EmployeeProfile.id == AttentionCase.employee_profile_id
        ).where(
            or_(
                EmployeeProfile.first_name.ilike(pattern, escape="\\"),
                EmployeeProfile.last_name.ilike(pattern, escape="\\"),
            )
        )
    rows = list(await db.scalars(statement))
    rows.sort(
        key=lambda item: (
            0 if item.case_type == "critical_allergen" else 1,
            item.created_at,
            str(item.id),
        )
    )
    filters = {
        "employee_profile_id": str(employee_profile_id) if employee_profile_id else None,
        "state": state,
        "case_type": case_type,
        "severity": severity,
        "location_id": str(location_id) if location_id else None,
        "employee_query": employee_query.strip() if employee_query else None,
    }
    start = 0
    if cursor is not None:
        key = _decode_cursor(cursor, filters)
        if len(key) != 3:
            raise _invalid_cursor()
        try:
            cursor_key = (
                int(str(key[0])),
                datetime.fromisoformat(str(key[1])),
                str(UUID(str(key[2]))),
            )
        except (TypeError, ValueError) as exc:
            raise _invalid_cursor() from exc
        start = next(
            (
                index
                for index, item in enumerate(rows)
                if (
                    0 if item.case_type == "critical_allergen" else 1,
                    item.created_at,
                    str(item.id),
                )
                > cursor_key
            ),
            len(rows),
        )
    page = rows[start : start + limit + 1]
    visible = page[:limit]
    next_cursor = None
    if len(page) > limit and visible:
        last = visible[-1]
        next_cursor = _encode_cursor(
            filters,
            [
                0 if last.case_type == "critical_allergen" else 1,
                last.created_at.isoformat(),
                str(last.id),
            ],
        )
    return AttentionCaseCollection(
        items=[await attention_response(db, item) for item in visible],
        next_cursor=next_cursor,
    )


async def _record_requirement_action(
    db: AsyncSession,
    *,
    requirement: RetakeRequirement,
    actor_user_id: UUID,
    action: str,
    now: datetime,
    comment: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        RetakeRequirementAction(
            organization_id=requirement.organization_id,
            location_id=requirement.location_id,
            retake_requirement_id=requirement.id,
            actor_type="user",
            actor_user_id=actor_user_id,
            action=action,
            attempt_id=None,
            comment=comment,
            details=details or {},
            created_at=now,
        )
    )


async def create_proposed_requirement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    reason: str,
    target_assessment_id: UUID | None,
    source_attention_case_id: UUID | None,
    management_source_key: str | None,
    target_policy: dict[str, object],
    due_at: datetime | None,
    now: datetime,
) -> RetakeRequirement:
    effective_due_at = due_at or now + timedelta(days=7)
    _require_aware(effective_due_at)
    employee = await db.scalar(
        select(EmployeeProfile).where(
            EmployeeProfile.id == employee_profile_id,
            EmployeeProfile.organization_id == organization_id,
        )
    )
    if employee is None or employee.location_id is None:
        raise _error(404, "RETAKE_TARGET_UNAVAILABLE", "Ціль перескладання недоступна.")

    source_case: AttentionCase | None = None
    if reason == "critical_error":
        source_case = await db.scalar(
            select(AttentionCase).where(
                AttentionCase.id == source_attention_case_id,
                AttentionCase.organization_id == organization_id,
                AttentionCase.location_id == employee.location_id,
                AttentionCase.employee_profile_id == employee.id,
                AttentionCase.case_type == "critical_allergen",
            )
        )
        if source_case is None:
            raise _attention_not_found()

    assessment: Assessment | None
    assignment: TrainingAssignment | None = None
    if target_assessment_id is None:
        # UI не повинен вимагати від адміністратора внутрішній UUID оцінювання:
        # сервер обирає Final Exam у перевіреному контексті джерела або поточного призначення.
        if source_case is not None:
            target_training_id = source_case.training_id
        else:
            assignment = await db.scalar(
                select(TrainingAssignment)
                .where(
                    TrainingAssignment.employee_profile_id == employee.id,
                    TrainingAssignment.organization_id == organization_id,
                    TrainingAssignment.location_id == employee.location_id,
                    TrainingAssignment.status != "revoked",
                )
                .order_by(TrainingAssignment.assigned_at.desc(), TrainingAssignment.id.desc())
                .limit(1)
            )
            if assignment is None:
                raise _error(404, "RETAKE_TARGET_UNAVAILABLE", "Ціль перескладання недоступна.")
            target_training_id = assignment.training_id
        assessment = await db.scalar(
            select(Assessment).where(
                Assessment.organization_id == organization_id,
                Assessment.location_id == employee.location_id,
                Assessment.training_id == target_training_id,
                Assessment.assessment_type == "menu_final_exam",
            )
        )
    else:
        assessment = await db.scalar(
            select(Assessment).where(
                Assessment.id == target_assessment_id,
                Assessment.organization_id == organization_id,
            )
        )
    if assessment is None or assessment.location_id != employee.location_id:
        raise _error(404, "RETAKE_TARGET_UNAVAILABLE", "Ціль перескладання недоступна.")
    if assignment is None or assignment.training_id != assessment.training_id:
        assignment = await db.scalar(
            select(TrainingAssignment)
            .where(
                TrainingAssignment.employee_profile_id == employee.id,
                TrainingAssignment.training_id == assessment.training_id,
                TrainingAssignment.organization_id == organization_id,
                TrainingAssignment.location_id == employee.location_id,
                TrainingAssignment.status != "revoked",
            )
            .order_by(TrainingAssignment.assigned_at.desc(), TrainingAssignment.id.desc())
            .limit(1)
        )
    if assignment is None:
        raise _error(404, "RETAKE_TARGET_UNAVAILABLE", "Ціль перескладання недоступна.")
    if reason == "critical_error" and (
        source_case is None or source_case.training_id != assessment.training_id
    ):
        raise _attention_not_found()
    normalized_source_key = management_source_key.strip() if management_source_key else None
    requirement_id = uuid4()
    inserted_id = await db.scalar(
        postgresql_insert(RetakeRequirement)
        .values(
            id=requirement_id,
            organization_id=organization_id,
            location_id=employee.location_id,
            training_id=assessment.training_id,
            employee_profile_id=employee.id,
            assignment_id=assignment.id,
            target_assessment_id=assessment.id,
            reason=reason,
            state="proposed",
            source_result_id=None,
            source_attempt_id=None,
            source_attention_case_id=source_attention_case_id,
            management_source_key=normalized_source_key,
            target_policy=target_policy,
            proposed_at=now,
            proposed_by_user_id=actor_user_id,
            confirmed_at=None,
            confirmed_by_user_id=None,
            due_at=effective_due_at,
            clock_frozen_at=None,
            frozen_seconds=0,
            completed_at=None,
            completion_attempt_id=None,
            cancelled_at=None,
            cancelled_by_user_id=None,
            cancellation_comment=None,
            revision=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing()
        .returning(RetakeRequirement.id)
    )
    if inserted_id is None:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Поточна вимога вже існує.")
    requirement = await db.get(RetakeRequirement, inserted_id)
    if requirement is None:
        raise RuntimeError("Inserted Retake Requirement is unavailable")
    await _record_requirement_action(
        db,
        requirement=requirement,
        actor_user_id=actor_user_id,
        action="proposed",
        now=now,
    )
    await db.flush()
    return requirement


async def update_proposed_due_at(
    db: AsyncSession,
    *,
    organization_id: UUID,
    requirement_id: UUID,
    actor_user_id: UUID,
    due_at: datetime,
    expected_revision: int,
    now: datetime,
) -> RetakeRequirement:
    _require_aware(due_at)
    requirement = await db.scalar(
        select(RetakeRequirement)
        .where(
            RetakeRequirement.id == requirement_id,
            RetakeRequirement.organization_id == organization_id,
        )
        .with_for_update()
    )
    if requirement is None:
        raise _requirement_not_found()
    if requirement.state != "proposed":
        raise _error(409, "RETAKE_REQUIREMENT_NOT_PROPOSED", "Вимога вже не є пропозицією.")
    if requirement.revision != expected_revision:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Версія вимоги змінилася.")
    previous_due_at = requirement.due_at
    requirement.due_at = due_at
    requirement.revision += 1
    await _record_requirement_action(
        db,
        requirement=requirement,
        actor_user_id=actor_user_id,
        action="proposed",
        now=now,
        details={"previous_due_at": previous_due_at.isoformat(), "due_at": due_at.isoformat()},
    )
    await db.flush()
    return requirement


async def confirm_requirement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    requirement_id: UUID,
    actor_user_id: UUID,
    expected_revision: int,
    now: datetime,
) -> RetakeRequirement:
    requirement = await db.scalar(
        select(RetakeRequirement)
        .where(
            RetakeRequirement.id == requirement_id,
            RetakeRequirement.organization_id == organization_id,
        )
        .with_for_update()
    )
    if requirement is None:
        raise _requirement_not_found()
    if requirement.state != "proposed":
        raise _error(409, "RETAKE_REQUIREMENT_NOT_PROPOSED", "Вимога вже не є пропозицією.")
    if requirement.revision != expected_revision:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Версія вимоги змінилася.")
    if requirement.due_at <= now:
        raise _error(422, "RETAKE_DUE_AT_INVALID", "Підтверджений дедлайн має бути в майбутньому.")
    requirement.state = "active"
    requirement.confirmed_at = now
    requirement.confirmed_by_user_id = actor_user_id
    requirement.revision += 1
    await _record_requirement_action(
        db,
        requirement=requirement,
        actor_user_id=actor_user_id,
        action="confirmed",
        now=now,
    )
    await db.flush()
    return requirement


async def cancel_requirement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    requirement_id: UUID,
    actor_user_id: UUID,
    expected_revision: int,
    comment: str,
    now: datetime,
) -> RetakeRequirement:
    normalized_comment = comment.strip()
    if not 1 <= len(normalized_comment) <= 500:
        raise _error(422, "VALIDATION_ERROR", "Для скасування потрібен змістовний коментар.")
    requirement = await db.scalar(
        select(RetakeRequirement)
        .where(
            RetakeRequirement.id == requirement_id,
            RetakeRequirement.organization_id == organization_id,
        )
        .with_for_update()
    )
    if requirement is None:
        raise _requirement_not_found()
    if requirement.state == "cancelled":
        return requirement
    if requirement.state not in {"proposed", "active"}:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Завершену вимогу не можна скасувати.")
    if requirement.revision != expected_revision:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Версія вимоги змінилася.")
    requirement.state = "cancelled"
    requirement.cancelled_at = now
    requirement.cancelled_by_user_id = actor_user_id
    requirement.cancellation_comment = normalized_comment
    requirement.revision += 1
    await _record_requirement_action(
        db,
        requirement=requirement,
        actor_user_id=actor_user_id,
        action="cancelled",
        now=now,
        comment=normalized_comment,
    )
    await resolve_terminal_overdue_case(
        db,
        requirement=requirement,
        resolution_type="requirement_cancelled",
        occurred_at=now,
    )
    await db.flush()
    return requirement


async def acknowledge_case(
    db: AsyncSession,
    *,
    organization_id: UUID,
    attention_id: UUID,
    actor_user_id: UUID,
    expected_revision: int,
    now: datetime,
) -> AttentionCase:
    case = await get_attention_case(
        db,
        organization_id=organization_id,
        attention_id=attention_id,
    )
    if case.revision != expected_revision:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Версія кейсу змінилася.")
    try:
        await acknowledge_attention_case(
            db,
            organization_id=organization_id,
            case_id=attention_id,
            actor_user_id=actor_user_id,
            now=now,
        )
    except ValueError as exc:
        raise _error(409, "ATTENTION_CASE_ALREADY_RESOLVED", "Кейс уже завершено.") from exc
    return case


async def resolve_case(
    db: AsyncSession,
    *,
    organization_id: UUID,
    attention_id: UUID,
    actor_user_id: UUID,
    expected_revision: int,
    resolution_type: str,
    comment: str | None,
    evidence_attempt_id: UUID | None,
    now: datetime,
) -> AttentionCase:
    case = await get_attention_case(
        db,
        organization_id=organization_id,
        attention_id=attention_id,
    )
    if case.revision != expected_revision:
        raise _error(409, "RETAKE_REQUIREMENT_CONFLICT", "Версія кейсу змінилася.")
    try:
        changed = await resolve_attention_case(
            db,
            organization_id=organization_id,
            case_id=attention_id,
            actor_user_id=actor_user_id,
            resolution_type=resolution_type,
            now=now,
            comment=comment,
            evidence_attempt_id=evidence_attempt_id,
        )
    except ValueError as exc:
        code = (
            "CLEAN_RETAKE_NOT_PROVEN"
            if resolution_type == "clean_retake"
            else "ATTENTION_RESOLUTION_INVALID"
        )
        raise _error(422, code, "Неможливо підтвердити завершення кейсу.") from exc
    if not changed:
        raise _error(409, "ATTENTION_CASE_ALREADY_RESOLVED", "Кейс уже завершено.")
    return case
