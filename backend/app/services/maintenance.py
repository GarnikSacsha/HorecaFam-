from datetime import datetime, timedelta
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentAttempt,
    AttemptDeviceLease,
    AuditEvent,
    BackgroundJob,
    EmailDelivery,
    JobAttempt,
    MfaChallenge,
    MfaRecoveryCode,
    PasswordResetToken,
    Session,
)

CronJobTask = Literal[
    "attempt-expiry",
    "retake-deadlines",
    "security-cleanup",
    "audit-retention",
]


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError("Maintenance timestamps must be timezone-aware")


def _cron_job_values(task: CronJobTask, now: datetime) -> tuple[str, dict[str, object], str]:
    hourly_bucket = now.replace(minute=0, second=0, microsecond=0).isoformat()
    if task == "attempt-expiry":
        return "attempt_expiry", {"cutoff_at": now.isoformat()}, f"attempt-expiry:{hourly_bucket}"
    if task == "retake-deadlines":
        return (
            "retake_deadline_projection",
            {"projected_at": now.isoformat()},
            f"retake-deadlines:{hourly_bucket}",
        )
    if task == "security-cleanup":
        cutoff_at = now - timedelta(days=30)
        return (
            "security_record_cleanup",
            {"cutoff_at": cutoff_at.isoformat()},
            f"security-cleanup:{now.date().isoformat()}",
        )
    cutoff_at = now - timedelta(days=365)
    return (
        "audit_retention",
        {"cutoff_at": cutoff_at.isoformat(), "dry_run": False},
        f"audit-retention:{now.date().isoformat()}",
    )


async def schedule_cron_task(
    db: AsyncSession,
    *,
    task: CronJobTask,
    now: datetime,
) -> BackgroundJob:
    _require_aware(now)
    job_type, payload, idempotency_key = _cron_job_values(task, now)
    job_id = uuid4()
    request_id = str(uuid4())
    inserted_id = await db.scalar(
        postgresql_insert(BackgroundJob)
        .values(
            id=job_id,
            organization_id=None,
            job_type=job_type,
            status="pending",
            payload=payload,
            request_id=request_id,
            idempotency_key=idempotency_key,
            priority=0,
            attempt_count=0,
            max_attempts=5,
            next_run_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=[BackgroundJob.job_type, BackgroundJob.idempotency_key]
        )
        .returning(BackgroundJob.id)
    )
    resolved_id = inserted_id
    if resolved_id is None:
        resolved_id = await db.scalar(
            select(BackgroundJob.id).where(
                BackgroundJob.job_type == job_type,
                BackgroundJob.idempotency_key == idempotency_key,
            )
        )
    if resolved_id is None:
        raise RuntimeError("Idempotent maintenance Job could not be resolved")
    job = await db.get(BackgroundJob, resolved_id)
    if job is None:
        raise RuntimeError("Scheduled maintenance Job is unavailable")
    return job


async def recover_stale_jobs(
    db: AsyncSession,
    *,
    now: datetime,
    lease_timeout: timedelta,
    batch_size: int = 100,
) -> list[UUID]:
    _require_aware(now)
    if lease_timeout <= timedelta(0) or batch_size < 1 or batch_size > 500:
        raise ValueError("Stale lease recovery bounds are invalid")
    stale_before = now - lease_timeout
    jobs = list(
        await db.scalars(
            select(BackgroundJob)
            .where(
                BackgroundJob.status == "processing",
                func.coalesce(BackgroundJob.heartbeat_at, BackgroundJob.locked_at) <= stale_before,
            )
            .order_by(BackgroundJob.heartbeat_at, BackgroundJob.locked_at, BackgroundJob.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    recovered: list[UUID] = []
    for job in jobs:
        attempt = await db.scalar(
            select(JobAttempt)
            .where(
                JobAttempt.job_id == job.id,
                JobAttempt.attempt_number == job.attempt_count,
            )
            .with_for_update()
        )
        exhausted = job.attempt_count >= job.max_attempts
        if attempt is None:
            attempt = JobAttempt(
                job_id=job.id,
                attempt_number=job.attempt_count,
                worker_id=job.locked_by or "unknown-worker",
                started_at=job.locked_at or now,
                heartbeat_last_seen_at=job.heartbeat_at,
                finished_at=now,
                outcome="failed" if exhausted else "interrupted",
                error_code="STALE_LEASE",
                error_message="Worker lease expired before Job finalization.",
                next_retry_at=None if exhausted else now,
            )
            db.add(attempt)
        else:
            attempt.finished_at = now
            attempt.outcome = "failed" if exhausted else "interrupted"
            attempt.error_code = "STALE_LEASE"
            attempt.error_message = "Worker lease expired before Job finalization."
            attempt.next_retry_at = None if exhausted else now
        job.status = "failed" if exhausted else "pending"
        job.failed_at = now if exhausted else None
        job.next_run_at = now
        job.last_error_code = "STALE_LEASE"
        job.last_error_message = "Worker lease expired before Job finalization."
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        recovered.append(job.id)
    await db.flush()
    return recovered


async def expire_attempts(
    db: AsyncSession,
    *,
    cutoff_at: datetime,
    batch_size: int = 500,
) -> int:
    _require_aware(cutoff_at)
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("Attempt expiry batch is outside the accepted bounds")
    attempts = list(
        await db.scalars(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.status == "in_progress",
                AssessmentAttempt.expires_at <= cutoff_at,
            )
            .order_by(AssessmentAttempt.expires_at, AssessmentAttempt.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    for attempt in attempts:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
    await db.flush()
    return len(attempts)


async def _delete_selected_ids(
    db: AsyncSession,
    *,
    model: type[Session] | type[MfaChallenge] | type[PasswordResetToken] | type[MfaRecoveryCode],
    ids: list[UUID],
) -> int:
    if not ids:
        return 0
    result = cast(CursorResult[Any], await db.execute(delete(model).where(model.id.in_(ids))))
    return result.rowcount


async def cleanup_security_records(
    db: AsyncSession,
    *,
    cutoff_at: datetime,
    batch_size: int = 500,
) -> dict[str, int]:
    _require_aware(cutoff_at)
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("Security cleanup batch is outside the accepted bounds")
    session_ids = list(
        await db.scalars(
            select(Session.id)
            .where(
                func.coalesce(Session.revoked_at, Session.absolute_expires_at) <= cutoff_at,
                ~select(AttemptDeviceLease.id)
                .where(AttemptDeviceLease.session_id == Session.id)
                .exists(),
            )
            .order_by(Session.absolute_expires_at, Session.id)
            .limit(batch_size)
        )
    )
    challenge_ids = list(
        await db.scalars(
            select(MfaChallenge.id)
            .where(func.coalesce(MfaChallenge.used_at, MfaChallenge.expires_at) <= cutoff_at)
            .order_by(MfaChallenge.expires_at, MfaChallenge.id)
            .limit(batch_size)
        )
    )
    reset_ids = list(
        await db.scalars(
            select(PasswordResetToken.id)
            .where(
                func.coalesce(
                    PasswordResetToken.used_at,
                    PasswordResetToken.revoked_at,
                    PasswordResetToken.expires_at,
                )
                <= cutoff_at,
                ~select(EmailDelivery.id)
                .where(EmailDelivery.password_reset_token_id == PasswordResetToken.id)
                .exists(),
            )
            .order_by(PasswordResetToken.expires_at, PasswordResetToken.id)
            .limit(batch_size)
        )
    )
    recovery_ids = list(
        await db.scalars(
            select(MfaRecoveryCode.id)
            .where(MfaRecoveryCode.used_at <= cutoff_at)
            .order_by(MfaRecoveryCode.used_at, MfaRecoveryCode.id)
            .limit(batch_size)
        )
    )
    counts = {
        "sessions": await _delete_selected_ids(db, model=Session, ids=session_ids),
        "mfa_challenges": await _delete_selected_ids(db, model=MfaChallenge, ids=challenge_ids),
        "password_reset_tokens": await _delete_selected_ids(
            db, model=PasswordResetToken, ids=reset_ids
        ),
        "mfa_recovery_codes": await _delete_selected_ids(
            db, model=MfaRecoveryCode, ids=recovery_ids
        ),
    }
    await db.flush()
    return counts


async def run_audit_retention(
    db: AsyncSession,
    *,
    cutoff_at: datetime,
    batch_size: int,
    request_id: UUID,
    dry_run: bool = False,
) -> int:
    _require_aware(cutoff_at)
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("Audit retention batch is outside the accepted bounds")
    event_ids = list(
        await db.scalars(
            select(AuditEvent.id)
            .where(AuditEvent.created_at < cutoff_at)
            .order_by(AuditEvent.created_at, AuditEvent.id)
            .limit(batch_size)
        )
    )
    deleted = len(event_ids) if dry_run else 0
    if event_ids and not dry_run:
        result = cast(
            CursorResult[Any],
            await db.execute(delete(AuditEvent).where(AuditEvent.id.in_(event_ids))),
        )
        deleted = result.rowcount
    db.add(
        AuditEvent(
            organization_id=None,
            actor_user_id=None,
            actor_type="cron",
            action="audit.retention_previewed" if dry_run else "audit.retention_completed",
            target_type="audit_event",
            target_id=None,
            old_values=None,
            new_values={"deleted_count": deleted, "cutoff_at": cutoff_at.isoformat()},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.flush()
    return deleted
