import base64
import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Select, and_, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AuditEvent
from app.schemas.operations import AuditEventListResponse, AuditEventResponse

AuditActorType = Literal["user", "system", "worker", "cron"]
FORBIDDEN_AUDIT_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "hash",
    "csrf",
    "mfa",
    "provider_body",
    "email_content",
    "correct_answer",
    "grading_key",
)


def _invalid_cursor() -> APIError:
    return APIError(
        status_code=422,
        code="INVALID_CURSOR",
        message="Некоректний курсор сторінки.",
    )


def _encode_cursor(created_at: datetime, event_id: UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(event_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        created_at = datetime.fromisoformat(payload["created_at"])
        event_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise _invalid_cursor() from None
    return created_at, event_id


def _is_forbidden_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in FORBIDDEN_AUDIT_KEY_PARTS)


def redact_audit_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_forbidden_key(str(key)):
                continue
            safe_item = redact_audit_values(item)
            if safe_item in ({}, []):
                continue
            redacted[str(key)] = safe_item
        return redacted
    if isinstance(value, list):
        return [redact_audit_values(item) for item in value]
    return value


def _response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        organization_id=event.organization_id,
        actor_user_id=event.actor_user_id,
        actor_type=event.actor_type,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        old_values=redact_audit_values(event.old_values),
        new_values=redact_audit_values(event.new_values),
        request_id=event.request_id,
        outcome=event.outcome,
        error_code=event.error_code,
        created_at=event.created_at,
    )


def _apply_filters(
    statement: Select[tuple[AuditEvent]],
    *,
    action: str | None,
    actor_type: AuditActorType | None,
    target_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    cursor: str | None,
) -> Select[tuple[AuditEvent]]:
    if action is not None:
        statement = statement.where(AuditEvent.action == action)
    if actor_type is not None:
        statement = statement.where(AuditEvent.actor_type == actor_type)
    if target_type is not None:
        statement = statement.where(AuditEvent.target_type == target_type)
    if created_from is not None:
        statement = statement.where(AuditEvent.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(AuditEvent.created_at <= created_to)
    if cursor is not None:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        statement = statement.where(
            tuple_(AuditEvent.created_at, AuditEvent.id) < (cursor_created_at, cursor_id)
        )
    return statement


async def _page(
    db: AsyncSession,
    *,
    statement: Select[tuple[AuditEvent]],
    limit: int,
) -> AuditEventListResponse:
    rows = list(
        await db.scalars(
            statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        next_cursor = _encode_cursor(visible[-1].created_at, visible[-1].id)
    return AuditEventListResponse(
        items=[_response(event) for event in visible],
        next_cursor=next_cursor,
    )


async def list_organization_audit_events(
    db: AsyncSession,
    *,
    organization_id: UUID,
    action: str | None,
    actor_type: AuditActorType | None,
    target_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    cursor: str | None,
    limit: int,
) -> AuditEventListResponse:
    statement = _apply_filters(
        select(AuditEvent).where(AuditEvent.organization_id == organization_id),
        action=action,
        actor_type=actor_type,
        target_type=target_type,
        created_from=created_from,
        created_to=created_to,
        cursor=cursor,
    )
    return await _page(db, statement=statement, limit=limit)


async def list_operator_audit_events(
    db: AsyncSession,
    *,
    action: str | None,
    actor_type: AuditActorType | None,
    target_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    cursor: str | None,
    limit: int,
) -> AuditEventListResponse:
    statement = _apply_filters(
        select(AuditEvent).where(
            or_(
                AuditEvent.actor_type.in_(("system", "worker", "cron")),
                and_(
                    AuditEvent.actor_type == "user",
                    AuditEvent.action.like("operator.%"),
                ),
            )
        ),
        action=action,
        actor_type=actor_type,
        target_type=target_type,
        created_from=created_from,
        created_to=created_to,
        cursor=cursor,
    )
    return await _page(db, statement=statement, limit=limit)
