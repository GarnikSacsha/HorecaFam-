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
