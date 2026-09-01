import base64
import hashlib
import json
import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AuditEvent, BackgroundJob, EmailDelivery, JobAttempt
from app.schemas.operations import (
    JobStatus,
    JobType,
    OperatorEmailDeliveryResponse,
    OperatorJobAttemptResponse,
    OperatorJobDetail,
    OperatorJobListResponse,
    OperatorJobRetryResponse,
    OperatorJobSummary,
)

SENSITIVE_MESSAGE_PATTERN = re.compile(
    r"password|token|secret|authorization|cookie|csrf|mfa|grading[_ -]?key|correct[_ -]?answer",
    re.IGNORECASE,
)


def _api_error(*, status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _safe_message(message: str | None) -> str | None:
    if message is None:
        return None
    if SENSITIVE_MESSAGE_PATTERN.search(message):
        return "[REDACTED]"
    return message[:500]


def _summary(job: BackgroundJob) -> OperatorJobSummary:
    return OperatorJobSummary(
        id=job.id,
        organization_id=job.organization_id,
        job_type=job.job_type,
        status=job.status,
        priority=job.priority,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        next_run_at=job.next_run_at,
        last_error_code=job.last_error_code,
        last_error_message=_safe_message(job.last_error_message),
        started_at=job.started_at,
        completed_at=job.completed_at,
        failed_at=job.failed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _encode_cursor(created_at: datetime, job_id: UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(job_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        created_at = datetime.fromisoformat(payload["created_at"])
        job_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise _api_error(
            status_code=422,
            code="INVALID_CURSOR",
            message="Некоректний курсор сторінки.",
        ) from None
    return created_at, job_id


async def list_operator_jobs(
    db: AsyncSession,
    *,
    status: JobStatus | None,
    job_type: JobType | None,
    organization_id: UUID | None,
    cursor: str | None,
    limit: int,
) -> OperatorJobListResponse:
    statement = select(BackgroundJob)
    if status is not None:
        statement = statement.where(BackgroundJob.status == status)
    if job_type is not None:
        statement = statement.where(BackgroundJob.job_type == job_type)
    if organization_id is not None:
        statement = statement.where(BackgroundJob.organization_id == organization_id)
    if cursor is not None:
        created_at, job_id = _decode_cursor(cursor)
        statement = statement.where(
            tuple_(BackgroundJob.created_at, BackgroundJob.id) < (created_at, job_id)
        )
    rows = list(
        await db.scalars(
            statement.order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc()).limit(
                limit + 1
            )
        )
    )
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        next_cursor = _encode_cursor(visible[-1].created_at, visible[-1].id)
    return OperatorJobListResponse(
        items=[_summary(job) for job in visible],
        next_cursor=next_cursor,
    )


async def get_operator_job(db: AsyncSession, *, job_id: UUID) -> OperatorJobDetail:
    job = await db.get(BackgroundJob, job_id)
    if job is None:
        raise _api_error(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="Ресурс не знайдено.",
        )
    attempts = list(
        await db.scalars(
            select(JobAttempt)
            .where(JobAttempt.job_id == job.id)
            .order_by(JobAttempt.attempt_number.desc())
        )
    )
    delivery = await db.scalar(select(EmailDelivery).where(EmailDelivery.job_id == job.id))
    summary = _summary(job)
    return OperatorJobDetail(
        **summary.model_dump(),
        request_id=UUID(job.request_id) if job.request_id is not None else None,
        locked_at=job.locked_at,
        heartbeat_at=job.heartbeat_at,
        attempts=[
            OperatorJobAttemptResponse(
                id=attempt.id,
                attempt_number=attempt.attempt_number,
                started_at=attempt.started_at,
                heartbeat_last_seen_at=attempt.heartbeat_last_seen_at,
                finished_at=attempt.finished_at,
                outcome=attempt.outcome,
                error_code=attempt.error_code,
                error_message=_safe_message(attempt.error_message),
                next_retry_at=attempt.next_retry_at,
            )
            for attempt in attempts
        ],
        delivery=(
            OperatorEmailDeliveryResponse(
                status=delivery.status,
                provider=delivery.provider,
                accepted_by_provider_at=delivery.accepted_by_provider_at,
                delivered_at=delivery.delivered_at,
                bounced_at=delivery.bounced_at,
                failed_at=delivery.failed_at,
                error_code=delivery.error_code,
            )
            if delivery is not None
            else None
        ),
    )


def _fingerprint(reason: str) -> str:
    return hashlib.sha256(
        json.dumps({"reason": reason}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def _retry_audits(db: AsyncSession, *, source_job_id: UUID) -> list[AuditEvent]:
    return list(
        await db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.action == "operator.job.retried",
                AuditEvent.target_type == "background_job",
                AuditEvent.target_id == source_job_id,
            )
            .order_by(AuditEvent.created_at, AuditEvent.id)
            .with_for_update()
        )
    )


async def retry_failed_job(
    db: AsyncSession,
    *,
    source_job_id: UUID,
    actor_user_id: UUID,
    reason: str,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> OperatorJobRetryResponse:
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
    fingerprint = _fingerprint(reason)
    # Блокування джерела серіалізує конкурентні retry без зміни append-only історії спроб.
    source = await db.scalar(
        select(BackgroundJob).where(BackgroundJob.id == source_job_id).with_for_update()
    )
    if source is None:
        raise _api_error(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="Ресурс не знайдено.",
        )
    audits = await _retry_audits(db, source_job_id=source_job_id)
    for event in audits:
        values = event.new_values or {}
        if values.get("idempotency_key_hash") != key_hash:
            continue
        if values.get("request_fingerprint") != fingerprint:
            raise _api_error(
                status_code=409,
                code="IDEMPOTENCY_KEY_REUSED",
                message="Ключ ідемпотентності вже використано для іншого запиту.",
            )
        retried_id = UUID(str(values["retried_job_id"]))
        retried = await db.get(BackgroundJob, retried_id)
        if retried is None:
            raise RuntimeError("Audited retry Job is unavailable")
        return OperatorJobRetryResponse(
            source_job_id=source_job_id,
            job=_summary(retried),
            replayed=True,
        )

    if source.status != "failed":
        raise _api_error(
            status_code=409,
            code="JOB_NOT_RETRYABLE",
            message="Повторити можна лише завершений з помилкою Job.",
        )
    if audits:
        raise _api_error(
            status_code=409,
            code="JOB_RETRY_ALREADY_CREATED",
            message="Для цього Job уже створено контрольований повтор.",
        )

    retried = BackgroundJob(
        organization_id=source.organization_id,
        job_type=source.job_type,
        status="pending",
        payload=dict(source.payload),
        request_id=str(request_id),
        idempotency_key=f"operator-retry:{source.id}:{key_hash[:16]}",
        priority=source.priority,
        attempt_count=0,
        max_attempts=source.max_attempts,
        next_run_at=now,
    )
    db.add(retried)
    await db.flush()
    source_delivery = await db.scalar(
        select(EmailDelivery).where(EmailDelivery.job_id == source.id).with_for_update()
    )
    if source_delivery is not None:
        db.add(
            EmailDelivery(
                organization_id=source_delivery.organization_id,
                job_id=retried.id,
                invitation_id=source_delivery.invitation_id,
                password_reset_token_id=source_delivery.password_reset_token_id,
                message_type=source_delivery.message_type,
                provider=source_delivery.provider,
                status="pending",
            )
        )
    db.add(
        AuditEvent(
            organization_id=source.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="operator.job.retried",
            target_type="background_job",
            target_id=source.id,
            old_values={"status": "failed"},
            new_values={
                "status": "pending",
                "retried_job_id": str(retried.id),
                "reason": reason,
                "idempotency_key_hash": key_hash,
                "request_fingerprint": fingerprint,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    await db.refresh(retried)
    return OperatorJobRetryResponse(
        source_job_id=source.id,
        job=_summary(retried),
        replayed=False,
    )
