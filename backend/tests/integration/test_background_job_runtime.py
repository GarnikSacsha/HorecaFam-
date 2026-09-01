import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.observability import configure_observability
from app.db.session import create_engine, create_session_factory
from app.models import BackgroundJob, BackgroundJobType, JobAttempt
from app.services.background_jobs import (
    ClaimedJob,
    LostJobLeaseError,
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
)
from app.worker import run_worker_once


def make_maintenance_job(
    *,
    now: datetime,
    idempotency_key: str,
    max_attempts: int = 5,
) -> BackgroundJob:
    return BackgroundJob(
        organization_id=None,
        job_type="attempt_expiry",
        status="pending",
        payload={"cutoff_at": now.isoformat()},
        idempotency_key=idempotency_key,
        request_id=str(uuid4()),
        max_attempts=max_attempts,
        next_run_at=now,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("job_type", "payload"),
    [
        ("attempt_expiry", {"cutoff_at": "2031-01-02T10:00:00Z"}),
        ("retake_deadline_projection", {"projected_at": "2031-01-02T10:00:00Z"}),
        ("security_record_cleanup", {"cutoff_at": "2030-12-03T10:00:00Z"}),
        ("audit_retention", {"cutoff_at": "2030-01-02T10:00:00Z", "dry_run": True}),
    ],
)
async def test_closed_maintenance_payload_catalogue_accepts_only_exact_fields(
    db_session: AsyncSession,
    job_type: str,
    payload: dict[str, object],
) -> None:
    db_session.add(
        BackgroundJob(
            job_type=job_type,
            status="pending",
            payload=payload,
            idempotency_key=f"{job_type}:valid",
        )
    )
    await db_session.commit()


@pytest.mark.integration
async def test_job_payload_rejects_unapproved_data(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        BackgroundJob(
            job_type="attempt_expiry",
            status="pending",
            payload={"cutoff_at": "2031-01-02T10:00:00Z", "raw_token": "forbidden"},
            idempotency_key="attempt_expiry:invalid",
            request_id=str(uuid4()),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.integration
async def test_job_request_correlation_requires_a_uuid(db_session: AsyncSession) -> None:
    job = make_maintenance_job(
        now=datetime.now(UTC),
        idempotency_key="attempt_expiry:invalid-request-id",
    )
    job.request_id = "not-a-request-uuid"
    db_session.add(job)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.integration
async def test_competing_workers_claim_one_job_once(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    now = datetime(2031, 1, 2, 10, 0, tzinfo=UTC)
    db_session.add(make_maintenance_job(now=now, idempotency_key="expiry:2031-01-02T10"))
    await db_session.commit()

    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)

    async def claim(worker_id: str) -> ClaimedJob | None:
        async with session_factory() as session, session.begin():
            return await claim_next_job(session, worker_id=worker_id, now=now)

    try:
        claims = await asyncio.gather(claim("worker-a"), claim("worker-b"))
    finally:
        await engine.dispose()

    claimed = [claim for claim in claims if claim is not None]
    assert len(claimed) == 1
    assert claimed[0].attempt_number == 1

    job = await db_session.scalar(select(BackgroundJob))
    attempt = await db_session.scalar(select(JobAttempt))
    assert job is not None
    assert attempt is not None
    assert job.status == "processing"
    assert job.attempt_count == 1
    assert attempt.job_id == job.id
    assert attempt.outcome == "processing"


@pytest.mark.integration
async def test_heartbeat_updates_the_owned_lease_and_lost_owner_cannot_finalize(
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, 10, 0, tzinfo=UTC)
    job = make_maintenance_job(now=now, idempotency_key="expiry:lease")
    db_session.add(job)
    await db_session.commit()

    claim = await claim_next_job(db_session, worker_id="worker-a", now=now)
    assert claim is not None
    heartbeat_at = now + timedelta(seconds=15)
    assert await heartbeat_job(
        db_session,
        job_id=claim.job_id,
        attempt_id=claim.attempt_id,
        worker_id="worker-a",
        now=heartbeat_at,
    )
    await db_session.commit()

    await db_session.refresh(job)
    assert job.heartbeat_at == heartbeat_at
    attempt = await db_session.get(JobAttempt, claim.attempt_id)
    assert attempt is not None
    assert attempt.heartbeat_last_seen_at == heartbeat_at

    job.locked_by = "worker-b"
    await db_session.commit()
    with pytest.raises(LostJobLeaseError):
        await complete_job(
            db_session,
            job_id=claim.job_id,
            attempt_id=claim.attempt_id,
            worker_id="worker-a",
            now=heartbeat_at + timedelta(seconds=1),
        )
    await db_session.rollback()
    await db_session.refresh(job)
    assert job.status == "processing"
    assert job.completed_at is None


@pytest.mark.integration
async def test_failure_retries_with_increasing_backoff_then_becomes_terminal(
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, 10, 0, tzinfo=UTC)
    job = make_maintenance_job(
        now=now,
        idempotency_key="expiry:retry",
        max_attempts=2,
    )
    db_session.add(job)
    await db_session.commit()

    first = await claim_next_job(db_session, worker_id="worker-a", now=now)
    assert first is not None
    first_result = await fail_job(
        db_session,
        job_id=first.job_id,
        attempt_id=first.attempt_id,
        worker_id="worker-a",
        now=now,
        error_code="TEMPORARY_FAILURE",
        error_message="Temporary handler failure.",
        jitter_seconds=7,
    )
    await db_session.commit()

    assert first_result.status == "pending"
    assert first_result.next_run_at == now + timedelta(seconds=67)
    first_attempt = await db_session.get(JobAttempt, first.attempt_id)
    assert first_attempt is not None
    assert first_attempt.outcome == "retry_scheduled"
    assert first_attempt.next_retry_at == first_result.next_run_at

    second = await claim_next_job(
        db_session,
        worker_id="worker-b",
        now=first_result.next_run_at,
    )
    assert second is not None
    assert second.attempt_number == 2
    second_result = await fail_job(
        db_session,
        job_id=second.job_id,
        attempt_id=second.attempt_id,
        worker_id="worker-b",
        now=first_result.next_run_at,
        error_code="TEMPORARY_FAILURE",
        error_message="Temporary handler failure.",
        jitter_seconds=0,
    )
    await db_session.commit()

    assert second_result.status == "failed"
    assert second_result.next_run_at is None
    await db_session.refresh(job)
    assert job.failed_at == first_result.next_run_at
    assert job.locked_by is None


@pytest.mark.integration
async def test_completed_attempt_is_immutable(
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, 10, 0, tzinfo=UTC)
    db_session.add(make_maintenance_job(now=now, idempotency_key="expiry:complete"))
    await db_session.commit()

    claim = await claim_next_job(db_session, worker_id="worker-a", now=now)
    assert claim is not None
    await complete_job(
        db_session,
        job_id=claim.job_id,
        attempt_id=claim.attempt_id,
        worker_id="worker-a",
        now=now + timedelta(seconds=1),
    )
    await db_session.commit()

    attempt = await db_session.get(JobAttempt, claim.attempt_id)
    assert attempt is not None
    assert attempt.outcome == "completed"
    attempt.error_message = "This finalized record must not change."
    with pytest.raises(DBAPIError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.integration
async def test_worker_runtime_completes_an_approved_handler(
    db_session: AsyncSession,
    migrated_test_database: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = datetime.now(UTC)
    job = make_maintenance_job(now=now, idempotency_key="expiry:worker-success")
    db_session.add(job)
    await db_session.commit()
    handled: list[ClaimedJob] = []

    async def handle(claimed: ClaimedJob) -> None:
        handled.append(claimed)

    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    configure_observability(migrated_test_database)
    app_logger = logging.getLogger("app")
    caplog.set_level(logging.INFO)
    app_logger.addHandler(caplog.handler)
    try:
        assert await run_worker_once(
            session_factory,
            worker_id="worker-a",
            handlers={BackgroundJobType.ATTEMPT_EXPIRY: handle},
            now=now,
        )
    finally:
        app_logger.removeHandler(caplog.handler)
        await engine.dispose()

    await db_session.refresh(job)
    assert [claim.job_id for claim in handled] == [job.id]
    assert job.status == "completed"
    lifecycle_records = [
        record for record in caplog.records if record.msg in {"job.claimed", "job.completed"}
    ]
    assert [record.msg for record in lifecycle_records] == ["job.claimed", "job.completed"]
    assert all(record.__dict__["job_id"] == job.id for record in lifecycle_records)
    assert all(record.__dict__["request_id"] == job.request_id for record in lifecycle_records)
    assert all("payload" not in record.__dict__ for record in lifecycle_records)


@pytest.mark.integration
async def test_worker_runtime_never_persists_raw_handler_exceptions(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    now = datetime.now(UTC)
    job = make_maintenance_job(now=now, idempotency_key="expiry:worker-failure")
    db_session.add(job)
    await db_session.commit()

    async def fail_with_secret(_claimed: ClaimedJob) -> None:
        raise RuntimeError("raw-password-reset-token")

    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        assert await run_worker_once(
            session_factory,
            worker_id="worker-a",
            handlers={BackgroundJobType.ATTEMPT_EXPIRY: fail_with_secret},
            now=now,
        )
    finally:
        await engine.dispose()

    await db_session.refresh(job)
    attempt = await db_session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
    assert attempt is not None
    assert job.status == "pending"
    assert job.last_error_code == "JOB_HANDLER_ERROR"
    assert job.last_error_message == "Approved Job handler failed."
    assert "raw-password-reset-token" not in (attempt.error_message or "")
