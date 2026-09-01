import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BackgroundJob, JobAttempt

ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class LostJobLeaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    attempt_id: UUID
    attempt_number: int
    organization_id: UUID | None
    job_type: str
    payload: dict[str, Any]
    request_id: str | None


@dataclass(frozen=True)
class JobFailureResult:
    status: Literal["pending", "failed"]
    next_run_at: datetime | None


def retry_delay_seconds(*, attempt_number: int, jitter_seconds: int | None = None) -> int:
    if attempt_number < 1 or attempt_number > 5:
        raise ValueError("Attempt number must be between one and five")
    base_seconds = min(60 * (2 ** (attempt_number - 1)), 3600)
    maximum_jitter = max(1, base_seconds // 4)
    if jitter_seconds is None:
        jitter_seconds = int(secrets.randbelow(maximum_jitter + 1))
    if jitter_seconds < 0 or jitter_seconds > maximum_jitter:
        raise ValueError("Retry jitter is outside the bounded range")
    return int(base_seconds + jitter_seconds)


async def claim_next_job(
    db: AsyncSession,
    *,
    worker_id: str,
    now: datetime,
) -> ClaimedJob | None:
    normalized_worker_id = worker_id.strip()
    if not normalized_worker_id or len(normalized_worker_id) > 255:
        raise ValueError("Worker ID must contain between one and 255 characters")

    job = await db.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.next_run_at <= now,
            BackgroundJob.attempt_count < BackgroundJob.max_attempts,
        )
        .order_by(
            BackgroundJob.priority.desc(),
            BackgroundJob.next_run_at,
            BackgroundJob.created_at,
            BackgroundJob.id,
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None

    job.attempt_count += 1
    job.status = "processing"
    job.locked_by = normalized_worker_id
    job.locked_at = now
    job.heartbeat_at = now
    job.started_at = job.started_at or now
    attempt = JobAttempt(
        job_id=job.id,
        attempt_number=job.attempt_count,
        worker_id=normalized_worker_id,
        started_at=now,
        heartbeat_last_seen_at=now,
        outcome="processing",
    )
    db.add(attempt)
    await db.flush()
    return ClaimedJob(
        job_id=job.id,
        attempt_id=attempt.id,
        attempt_number=attempt.attempt_number,
        organization_id=job.organization_id,
        job_type=job.job_type,
        payload=dict(job.payload),
        request_id=job.request_id,
    )


async def _locked_owned_lease(
    db: AsyncSession,
    *,
    job_id: UUID,
    attempt_id: UUID,
    worker_id: str,
) -> tuple[BackgroundJob, JobAttempt]:
    job = await db.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update())
    if (
        job is None
        or job.status != "processing"
        or job.locked_by != worker_id
        or job.attempt_count < 1
    ):
        raise LostJobLeaseError("Job lease is no longer owned by this worker")
    attempt = await db.scalar(
        select(JobAttempt)
        .where(
            JobAttempt.id == attempt_id,
            JobAttempt.job_id == job.id,
            JobAttempt.attempt_number == job.attempt_count,
            JobAttempt.worker_id == worker_id,
            JobAttempt.outcome == "processing",
            JobAttempt.finished_at.is_(None),
        )
        .with_for_update()
    )
    if attempt is None:
        raise LostJobLeaseError("Job attempt is no longer writable by this worker")
    return job, attempt


async def heartbeat_job(
    db: AsyncSession,
    *,
    job_id: UUID,
    attempt_id: UUID,
    worker_id: str,
    now: datetime,
) -> bool:
    try:
        job, attempt = await _locked_owned_lease(
            db,
            job_id=job_id,
            attempt_id=attempt_id,
            worker_id=worker_id,
        )
    except LostJobLeaseError:
        return False
    job.heartbeat_at = now
    attempt.heartbeat_last_seen_at = now
    await db.flush()
    return True


def _clear_lease(job: BackgroundJob) -> None:
    job.locked_by = None
    job.locked_at = None
    job.heartbeat_at = None


async def complete_job(
    db: AsyncSession,
    *,
    job_id: UUID,
    attempt_id: UUID,
    worker_id: str,
    now: datetime,
) -> None:
    job, attempt = await _locked_owned_lease(
        db,
        job_id=job_id,
        attempt_id=attempt_id,
        worker_id=worker_id,
    )
    job.status = "completed"
    job.completed_at = now
    job.failed_at = None
    job.last_error_code = None
    job.last_error_message = None
    _clear_lease(job)
    attempt.finished_at = now
    attempt.outcome = "completed"
    await db.flush()


async def fail_job(
    db: AsyncSession,
    *,
    job_id: UUID,
    attempt_id: UUID,
    worker_id: str,
    now: datetime,
    error_code: str,
    error_message: str,
    jitter_seconds: int | None = None,
) -> JobFailureResult:
    if ERROR_CODE_PATTERN.fullmatch(error_code) is None:
        raise ValueError("Job error code must be a stable uppercase code")
    normalized_message = " ".join(error_message.split())
    if not normalized_message or len(normalized_message) > 500:
        raise ValueError("Job error message must contain between one and 500 characters")

    job, attempt = await _locked_owned_lease(
        db,
        job_id=job_id,
        attempt_id=attempt_id,
        worker_id=worker_id,
    )
    exhausted = job.attempt_count >= job.max_attempts
    next_run_at = None
    if exhausted:
        job.status = "failed"
        job.failed_at = now
        attempt.outcome = "failed"
    else:
        delay = retry_delay_seconds(
            attempt_number=job.attempt_count,
            jitter_seconds=jitter_seconds,
        )
        next_run_at = now + timedelta(seconds=delay)
        job.status = "pending"
        job.next_run_at = next_run_at
        job.failed_at = None
        attempt.outcome = "retry_scheduled"
        attempt.next_retry_at = next_run_at
    job.last_error_code = error_code
    job.last_error_message = normalized_message
    _clear_lease(job)
    attempt.finished_at = now
    attempt.error_code = error_code
    attempt.error_message = normalized_message
    await db.flush()
    return JobFailureResult(status="failed" if exhausted else "pending", next_run_at=next_run_at)
