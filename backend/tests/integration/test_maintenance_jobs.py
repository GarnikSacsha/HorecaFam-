from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEvent,
    BackgroundJob,
    JobAttempt,
    MfaChallenge,
    PasswordResetToken,
    Session,
)
from app.services.background_jobs import claim_next_job
from app.services.maintenance import (
    cleanup_security_records,
    expire_attempts,
    recover_stale_jobs,
    run_audit_retention,
    schedule_cron_task,
)
from tests.factories import make_user


@pytest.mark.integration
async def test_cron_replay_schedules_one_exact_maintenance_job(
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, 10, 13, tzinfo=UTC)
    first = await schedule_cron_task(db_session, task="attempt-expiry", now=now)
    second = await schedule_cron_task(
        db_session,
        task="attempt-expiry",
        now=now + timedelta(minutes=20),
    )
    await db_session.commit()

    assert first.id == second.id
    assert first.job_type == "attempt_expiry"
    assert first.payload == {"cutoff_at": now.isoformat()}
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 1


@pytest.mark.integration
async def test_stale_lease_recovery_records_interrupted_attempt_and_requeues(
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, 10, 0, tzinfo=UTC)
    job = BackgroundJob(
        job_type="attempt_expiry",
        status="pending",
        payload={"cutoff_at": now.isoformat()},
        idempotency_key="attempt-expiry:stale",
        next_run_at=now - timedelta(minutes=10),
    )
    db_session.add(job)
    await db_session.commit()
    claim = await claim_next_job(
        db_session,
        worker_id="stale-worker",
        now=now - timedelta(minutes=10),
    )
    assert claim is not None
    await db_session.commit()

    recovered = await recover_stale_jobs(
        db_session,
        now=now,
        lease_timeout=timedelta(minutes=5),
    )
    await db_session.commit()

    assert recovered == [job.id]
    await db_session.refresh(job)
    attempt = await db_session.get(JobAttempt, claim.attempt_id)
    assert attempt is not None
    assert job.status == "pending"
    assert job.next_run_at == now
    assert job.locked_by is None
    assert attempt.outcome == "interrupted"
    assert attempt.error_code == "STALE_LEASE"
    assert attempt.next_retry_at == now


@pytest.mark.integration
async def test_security_cleanup_obeys_terminal_grace_and_preserves_live_records(
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, 10, 0, tzinfo=UTC)
    cutoff = now - timedelta(days=30)
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    old_session = Session(
        user_id=user.id,
        token_hash="a" * 64,
        csrf_token_hash="b" * 64,
        created_at=cutoff - timedelta(days=2),
        last_seen_at=cutoff - timedelta(days=2),
        absolute_expires_at=cutoff - timedelta(days=1),
    )
    live_session = Session(
        user_id=user.id,
        token_hash="c" * 64,
        csrf_token_hash="d" * 64,
        created_at=now - timedelta(days=1),
        last_seen_at=now - timedelta(days=1),
        absolute_expires_at=now + timedelta(days=1),
    )
    old_challenge = MfaChallenge(
        user_id=user.id,
        token_hash="e" * 64,
        created_at=cutoff - timedelta(days=2),
        expires_at=cutoff - timedelta(days=1),
        used_at=cutoff - timedelta(days=1),
    )
    live_challenge = MfaChallenge(
        user_id=user.id,
        token_hash="f" * 64,
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    old_reset = PasswordResetToken(
        user_id=user.id,
        token_hash="1" * 64,
        created_at=cutoff - timedelta(days=2),
        expires_at=cutoff - timedelta(days=1),
        used_at=cutoff - timedelta(days=1),
    )
    live_reset = PasswordResetToken(
        user_id=user.id,
        token_hash="2" * 64,
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    db_session.add_all(
        [old_session, live_session, old_challenge, live_challenge, old_reset, live_reset]
    )
    await db_session.commit()

    counts = await cleanup_security_records(db_session, cutoff_at=cutoff, batch_size=100)
    await db_session.commit()

    assert counts == {
        "sessions": 1,
        "mfa_challenges": 1,
        "password_reset_tokens": 1,
        "mfa_recovery_codes": 0,
        "auth_rate_limit_buckets": 0,
        "invitation_rate_limit_buckets": 0,
    }
    assert await db_session.get(Session, old_session.id) is None
    assert await db_session.get(MfaChallenge, old_challenge.id) is None
    assert await db_session.get(PasswordResetToken, old_reset.id) is None
    assert await db_session.get(Session, live_session.id) is not None
    assert await db_session.get(MfaChallenge, live_challenge.id) is not None
    assert await db_session.get(PasswordResetToken, live_reset.id) is not None


@pytest.mark.integration
async def test_audit_retention_deletes_only_bounded_old_rows_and_appends_summary(
    db_session: AsyncSession,
) -> None:
    cutoff = datetime(2030, 1, 1, tzinfo=UTC)
    old_event = AuditEvent(
        actor_type="system",
        action="old.event",
        target_type="test",
        target_id=None,
        request_id=None,
        outcome="success",
        created_at=cutoff - timedelta(seconds=1),
    )
    current_event = AuditEvent(
        actor_type="system",
        action="current.event",
        target_type="test",
        target_id=None,
        request_id=None,
        outcome="success",
        created_at=cutoff,
    )
    db_session.add_all([old_event, current_event])
    await db_session.commit()

    deleted = await run_audit_retention(
        db_session,
        cutoff_at=cutoff,
        batch_size=1,
        request_id=uuid4(),
    )
    await db_session.commit()

    assert deleted == 1
    assert await db_session.get(AuditEvent, old_event.id) is None
    assert await db_session.get(AuditEvent, current_event.id) is not None
    summary = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "audit.retention_completed")
    )
    assert summary is not None
    assert summary.new_values == {"deleted_count": 1, "cutoff_at": cutoff.isoformat()}


@pytest.mark.parametrize("task", ["expiry", "security", "audit", "stale"])
@pytest.mark.parametrize("invalid", ["naive", "zero_batch", "large_batch"])
async def test_invalid_maintenance_bounds_have_no_effect(
    db_session: AsyncSession, task: str, invalid: str
) -> None:
    now = datetime(2031, 1, 2, tzinfo=UTC)
    if invalid == "naive":
        now = now.replace(tzinfo=None)
    batch = {"naive": 1, "zero_batch": 0, "large_batch": 1001}[invalid]
    with pytest.raises(ValueError):
        if task == "expiry":
            await expire_attempts(db_session, cutoff_at=now, batch_size=batch)
        elif task == "security":
            await cleanup_security_records(db_session, cutoff_at=now, batch_size=batch)
        elif task == "audit":
            await run_audit_retention(
                db_session, cutoff_at=now, batch_size=batch, request_id=uuid4()
            )
        else:
            await recover_stale_jobs(
                db_session, now=now, batch_size=batch, lease_timeout=timedelta(minutes=5)
            )
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 0


@pytest.mark.parametrize("seconds", [0, -1])
async def test_stale_recovery_requires_positive_lease_timeout(
    db_session: AsyncSession, seconds: int
) -> None:
    with pytest.raises(ValueError, match="bounds"):
        await recover_stale_jobs(
            db_session,
            now=datetime(2031, 1, 2, tzinfo=UTC),
            lease_timeout=timedelta(seconds=seconds),
        )
    assert await db_session.scalar(select(func.count()).select_from(JobAttempt)) == 0


@pytest.mark.parametrize("missing_attempt", [False, True])
async def test_exhausted_stale_job_is_terminal_at_exact_lease_boundary(
    db_session: AsyncSession, missing_attempt: bool
) -> None:
    now = datetime(2031, 1, 2, tzinfo=UTC)
    job = await schedule_cron_task(db_session, task="attempt-expiry", now=now)
    job.max_attempts = 1
    await db_session.commit()
    if missing_attempt:
        job.status = "processing"
        job.attempt_count = 1
        job.locked_by = "stale-worker"
        job.locked_at = job.heartbeat_at = job.started_at = now
    else:
        claim = await claim_next_job(db_session, worker_id="stale-worker", now=now)
        assert claim is not None
    await db_session.commit()
    recovered = await recover_stale_jobs(
        db_session, now=now + timedelta(minutes=5), lease_timeout=timedelta(minutes=5)
    )
    await db_session.commit()
    assert recovered == [job.id]
    await db_session.refresh(job)
    assert job.status == "failed" and job.failed_at == now + timedelta(minutes=5)
    assert job.locked_by is None and job.heartbeat_at is None
    attempt = await db_session.scalar(select(JobAttempt).where(JobAttempt.job_id == job.id))
    assert attempt is not None and attempt.outcome == "failed"
    assert attempt.error_code == "STALE_LEASE" and attempt.next_retry_at is None
    assert (
        await recover_stale_jobs(
            db_session, now=now + timedelta(minutes=10), lease_timeout=timedelta(minutes=5)
        )
        == []
    )


@pytest.mark.parametrize("with_old_row", [False, True])
async def test_retention_preview_preserves_rows_and_records_exact_count(
    db_session: AsyncSession, with_old_row: bool
) -> None:
    cutoff = datetime(2031, 1, 2, tzinfo=UTC)
    if with_old_row:
        db_session.add(
            AuditEvent(
                actor_type="system",
                action="old.event",
                target_type="test",
                outcome="success",
                created_at=cutoff - timedelta(seconds=1),
            )
        )
        await db_session.commit()
    count = await run_audit_retention(
        db_session, cutoff_at=cutoff, batch_size=1, request_id=uuid4(), dry_run=True
    )
    await db_session.commit()
    assert count == int(with_old_row)
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == count + 1
    summary = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "audit.retention_previewed")
    )
    assert summary is not None and summary.new_values is not None
    assert summary.new_values["deleted_count"] == count
