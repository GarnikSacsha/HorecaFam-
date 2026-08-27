import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import ApiIdempotencyRecord

IDEMPOTENCY_LIFETIME = timedelta(hours=24)


@dataclass(frozen=True)
class IdempotencyDecision:
    record: ApiIdempotencyRecord
    replayed: bool


def request_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def reserve_idempotency(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    action: str,
    key: str,
    fingerprint: str,
    resource_type: str,
    resource_id: UUID,
    response_status: int,
    now: datetime,
) -> IdempotencyDecision:
    candidate_id = uuid4()
    inserted_id = await db.scalar(
        insert(ApiIdempotencyRecord)
        .values(
            id=candidate_id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            key=key,
            request_fingerprint=fingerprint,
            resource_type=resource_type,
            resource_id=resource_id,
            response_status=response_status,
            expires_at=now + IDEMPOTENCY_LIFETIME,
        )
        .on_conflict_do_nothing(constraint="uq_api_idempotency_scope_action_key")
        .returning(ApiIdempotencyRecord.id)
    )
    if inserted_id is not None:
        record = await db.get(ApiIdempotencyRecord, inserted_id)
        if record is None:
            raise RuntimeError("Inserted idempotency record is unavailable")
        return IdempotencyDecision(record=record, replayed=False)

    record = await db.scalar(
        select(ApiIdempotencyRecord)
        .where(
            ApiIdempotencyRecord.organization_id == organization_id,
            ApiIdempotencyRecord.actor_user_id == actor_user_id,
            ApiIdempotencyRecord.action == action,
            ApiIdempotencyRecord.key == key,
        )
        .with_for_update()
    )
    if record is None:
        raise RuntimeError("Conflicting idempotency record is unavailable")
    if record.expires_at <= now:
        record.request_fingerprint = fingerprint
        record.resource_type = resource_type
        record.resource_id = resource_id
        record.response_status = response_status
        record.created_at = now
        record.expires_at = now + IDEMPOTENCY_LIFETIME
        return IdempotencyDecision(record=record, replayed=False)
    if record.request_fingerprint != fingerprint:
        raise APIError(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message="Ключ ідемпотентності вже використано для іншого запиту.",
        )
    return IdempotencyDecision(record=record, replayed=True)
