import base64
import binascii
import json
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AssessmentAttempt, AttentionCase, RetakeRequirement
from app.schemas.attention import (
    EmployeeAttentionSummary,
    EmployeeRetakeRequirementCollection,
    EmployeeRetakeRequirementResponse,
)
from app.services.retakes import retake_timing_state


def _invalid_cursor() -> APIError:
    return APIError(status_code=422, code="INVALID_CURSOR", message="Некоректний курсор сторінки.")


def _encode_cursor(key: tuple[int, datetime, UUID]) -> str:
    payload = json.dumps(
        [key[0], key[1].isoformat(), str(key[2])],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[int, datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(f"{cursor}{padding}").decode())
        if not isinstance(value, list) or len(value) != 3:
            raise ValueError
        parsed = (int(str(value[0])), datetime.fromisoformat(str(value[1])), UUID(str(value[2])))
        if parsed[1].tzinfo is None:
            raise ValueError
        return parsed
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _invalid_cursor() from exc


async def employee_requirement_response(
    db: AsyncSession,
    requirement: RetakeRequirement,
    *,
    now: datetime,
) -> EmployeeRetakeRequirementResponse:
    active_attempt = None
    if requirement.state == "active":
        active_attempt = await db.scalar(
            select(AssessmentAttempt.id).where(
                AssessmentAttempt.employee_profile_id == requirement.employee_profile_id,
                AssessmentAttempt.training_id == requirement.training_id,
                AssessmentAttempt.status == "in_progress",
            )
        )
    timing = retake_timing_state(requirement, now)
    if requirement.state == "active" and timing == "frozen":
        action = "wait"
    elif requirement.state == "active" and active_attempt is not None:
        action = "resume_retake"
    elif requirement.state == "active":
        action = "start_retake"
    else:
        action = "review_history"
    return EmployeeRetakeRequirementResponse(
        id=requirement.id,
        training_id=requirement.training_id,
        target_assessment_id=requirement.target_assessment_id,
        reason=requirement.reason,
        state=requirement.state,
        timing_state=timing,
        due_at=requirement.due_at,
        permitted_action=action,
        source_attempt_id=requirement.source_attempt_id,
        completion_attempt_id=requirement.completion_attempt_id,
        completed_at=requirement.completed_at,
        cancelled_at=requirement.cancelled_at,
    )


async def current_employee_requirement(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    training_id: UUID,
    target_assessment_id: UUID | None,
) -> RetakeRequirement | None:
    statement = select(RetakeRequirement).where(
        RetakeRequirement.organization_id == organization_id,
        RetakeRequirement.location_id == location_id,
        RetakeRequirement.employee_profile_id == employee_profile_id,
        RetakeRequirement.training_id == training_id,
        RetakeRequirement.state == "active",
    )
    if target_assessment_id is not None:
        statement = statement.where(RetakeRequirement.target_assessment_id == target_assessment_id)
    return cast(
        RetakeRequirement | None,
        await db.scalar(
            statement.order_by(RetakeRequirement.confirmed_at, RetakeRequirement.id).limit(1)
        ),
    )


async def employee_attention_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID,
    training_id: UUID | None = None,
) -> EmployeeAttentionSummary:
    statement = select(AttentionCase.case_type, func.count()).where(
        AttentionCase.organization_id == organization_id,
        AttentionCase.employee_profile_id == employee_profile_id,
        AttentionCase.state.in_(("open", "acknowledged")),
    )
    if training_id is not None:
        statement = statement.where(AttentionCase.training_id == training_id)
    rows = list((await db.execute(statement.group_by(AttentionCase.case_type))).tuples().all())
    counts = {case_type: count for case_type, count in rows}
    return EmployeeAttentionSummary(
        open_count=sum(counts.values()),
        has_critical_follow_up=counts.get("critical_allergen", 0) > 0,
        has_overdue_follow_up=counts.get("retake_overdue", 0) > 0,
    )


async def list_employee_requirements(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    now: datetime,
    cursor: str | None,
    limit: int,
) -> EmployeeRetakeRequirementCollection:
    rows = list(
        await db.scalars(
            select(RetakeRequirement).where(
                RetakeRequirement.organization_id == organization_id,
                RetakeRequirement.location_id == location_id,
                RetakeRequirement.employee_profile_id == employee_profile_id,
                RetakeRequirement.state != "proposed",
            )
        )
    )
    state_priority = {"active": 0, "completed": 1, "cancelled": 2}
    rows.sort(key=lambda item: (state_priority[item.state], item.due_at, item.id))
    start = 0
    if cursor is not None:
        cursor_key = _decode_cursor(cursor)
        start = next(
            (
                index
                for index, item in enumerate(rows)
                if (state_priority[item.state], item.due_at, item.id) > cursor_key
            ),
            len(rows),
        )
    page = rows[start : start + limit + 1]
    visible = page[:limit]
    next_cursor = None
    if len(page) > limit and visible:
        last = visible[-1]
        next_cursor = _encode_cursor((state_priority[last.state], last.due_at, last.id))
    return EmployeeRetakeRequirementCollection(
        items=[await employee_requirement_response(db, item, now=now) for item in visible],
        next_cursor=next_cursor,
    )
