import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, BackgroundJob, JobAttempt, Organization, Session
from app.security.tokens import hash_secret
from tests.factories.auth import make_admin_access
from tests.factories.identity import make_organization, make_user

FIXED_NOW = datetime(2031, 2, 3, 12, 0, tzinfo=UTC)


async def _arrange_elevated_session(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    *,
    scope: str,
    organization_id: UUID | None = None,
) -> tuple[UUID, str]:
    app.state.clock = lambda: FIXED_NOW
    user = make_user(email_normalized=f"operations-{uuid4()}@example.com")
    db.add(user)
    await db.flush()
    organization = (
        await db.get_one(Organization, organization_id) if organization_id is not None else None
    )
    db.add(make_admin_access(user, scope=scope, organization=organization))
    raw_session = f"operations-session-{uuid4()}"
    csrf_token = f"operations-csrf-{uuid4()}"
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(csrf_token),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
            mfa_verified_at=FIXED_NOW,
        )
    )
    await db.commit()
    client.cookies.set("horeca_session", raw_session, path="/api/v1")
    return user.id, csrf_token


async def test_organization_audit_is_tenant_scoped_cursor_paginated_and_redacted(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    own = make_organization(name="Own audit organization")
    foreign = make_organization(name="Foreign audit organization")
    db_session.add_all([own, foreign])
    await db_session.flush()
    admin_id, _csrf = await _arrange_elevated_session(
        auth_client,
        auth_app,
        db_session,
        scope="organization_admin",
        organization_id=own.id,
    )
    own_events = [
        AuditEvent(
            organization_id=own.id,
            actor_user_id=admin_id,
            actor_type="user",
            action="employee.paused",
            target_type="employee_profile",
            target_id=uuid4(),
            old_values=None,
            new_values={
                "reason_code": "leave",
                "password": "must-not-leak",
                "nested": {"token": "must-not-leak-either"},
            },
            request_id=uuid4(),
            outcome="success",
            created_at=FIXED_NOW,
        ),
        AuditEvent(
            organization_id=own.id,
            actor_user_id=admin_id,
            actor_type="user",
            action="employee.resumed",
            target_type="employee_profile",
            target_id=uuid4(),
            old_values=None,
            new_values={"reason_code": "returned"},
            request_id=uuid4(),
            outcome="success",
            created_at=FIXED_NOW - timedelta(minutes=1),
        ),
    ]
    db_session.add_all(
        [
            *own_events,
            AuditEvent(
                organization_id=foreign.id,
                actor_user_id=admin_id,
                actor_type="user",
                action="employee.disabled",
                target_type="employee_profile",
                target_id=uuid4(),
                old_values=None,
                new_values=None,
                request_id=uuid4(),
                outcome="success",
                created_at=FIXED_NOW + timedelta(minutes=1),
            ),
        ]
    )
    await db_session.commit()

    first = await auth_client.get(
        f"/api/v1/organizations/{own.id}/audit-events",
        params={"action": "employee.paused", "limit": 1},
    )

    assert first.status_code == 200
    body = first.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["organization_id"] == str(own.id)
    assert body["items"][0]["new_values"] == {"reason_code": "leave"}
    assert "must-not-leak" not in first.text
    assert "password" not in first.text
    assert "token" not in first.text

    unfiltered = await auth_client.get(
        f"/api/v1/organizations/{own.id}/audit-events",
        params={"limit": 1},
    )
    assert unfiltered.status_code == 200
    assert unfiltered.json()["next_cursor"] is not None
    second = await auth_client.get(
        f"/api/v1/organizations/{own.id}/audit-events",
        params={"limit": 1, "cursor": unfiltered.json()["next_cursor"]},
    )
    assert second.status_code == 200
    assert second.json()["items"][0]["id"] == str(own_events[1].id)

    hidden = await auth_client.get(f"/api/v1/organizations/{foreign.id}/audit-events")
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_operator_jobs_audit_and_failed_retry_are_safe_and_idempotent(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    operator_id, csrf_token = await _arrange_elevated_session(
        auth_client,
        auth_app,
        db_session,
        scope="platform_operator",
    )
    failed_job = BackgroundJob(
        organization_id=None,
        job_type="attempt_expiry",
        status="failed",
        payload={"cutoff_at": FIXED_NOW.isoformat()},
        request_id=str(uuid4()),
        idempotency_key="attempt-expiry:failed-secret-boundary",
        attempt_count=5,
        max_attempts=5,
        next_run_at=FIXED_NOW,
        last_error_code="JOB_HANDLER_ERROR",
        last_error_message="Safe bounded failure.",
        started_at=FIXED_NOW - timedelta(minutes=5),
        failed_at=FIXED_NOW - timedelta(minutes=1),
    )
    db_session.add(failed_job)
    await db_session.flush()
    db_session.add_all(
        [
            JobAttempt(
                job_id=failed_job.id,
                attempt_number=5,
                worker_id="worker-safe",
                started_at=FIXED_NOW - timedelta(minutes=2),
                finished_at=FIXED_NOW - timedelta(minutes=1),
                outcome="failed",
                error_code="JOB_HANDLER_ERROR",
                error_message="Safe bounded failure.",
            ),
            AuditEvent(
                organization_id=None,
                actor_user_id=None,
                actor_type="cron",
                action="audit.retention_completed",
                target_type="audit_event",
                target_id=None,
                old_values=None,
                new_values={"deleted_count": 0},
                request_id=uuid4(),
                outcome="success",
                created_at=FIXED_NOW,
            ),
        ]
    )
    await db_session.commit()

    listed = await auth_client.get("/api/v1/operator/jobs", params={"status": "failed"})
    detail = await auth_client.get(f"/api/v1/operator/jobs/{failed_job.id}")
    audit = await auth_client.get("/api/v1/operator/audit-events")

    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == str(failed_job.id)
    assert detail.status_code == 200
    assert detail.json()["attempts"][0]["outcome"] == "failed"
    forbidden = {"payload", "idempotency_key", "locked_by", "worker_id"}
    assert forbidden.isdisjoint(detail.json())
    assert forbidden.isdisjoint(detail.json()["attempts"][0])
    assert "failed-secret-boundary" not in detail.text
    assert audit.status_code == 200
    assert [item["action"] for item in audit.json()["items"]] == ["audit.retention_completed"]

    headers = {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf_token,
        "Idempotency-Key": "retry-failed-job",
    }
    first_retry = await auth_client.post(
        f"/api/v1/operator/jobs/{failed_job.id}/retry",
        headers=headers,
        json={"reason": "Reviewed transient worker failure"},
    )
    replay = await auth_client.post(
        f"/api/v1/operator/jobs/{failed_job.id}/retry",
        headers=headers,
        json={"reason": "Reviewed transient worker failure"},
    )

    assert first_retry.status_code == 200
    assert first_retry.json()["source_job_id"] == str(failed_job.id)
    assert first_retry.json()["job"]["status"] == "pending"
    assert first_retry.json()["job"]["id"] != str(failed_job.id)
    assert first_retry.json()["replayed"] is False
    assert replay.status_code == 200
    assert replay.json()["job"]["id"] == first_retry.json()["job"]["id"]
    assert replay.json()["replayed"] is True
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "operator.job.retried",
                AuditEvent.actor_user_id == operator_id,
            )
        )
        == 1
    )

    pending_retry = await auth_client.post(
        f"/api/v1/operator/jobs/{first_retry.json()['job']['id']}/retry",
        headers={**headers, "Idempotency-Key": "retry-pending-job"},
        json={"reason": "Must remain failed-only"},
    )
    assert pending_retry.status_code == 409
    assert pending_retry.json()["code"] == "JOB_NOT_RETRYABLE"


async def test_operations_routes_are_declared_and_operator_retry_requires_csrf(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    _operator_id, _csrf = await _arrange_elevated_session(
        auth_client,
        auth_app,
        db_session,
        scope="platform_operator",
    )
    job = BackgroundJob(
        job_type="attempt_expiry",
        status="failed",
        payload={"cutoff_at": FIXED_NOW.isoformat()},
        idempotency_key="attempt-expiry:csrf",
        attempt_count=5,
        max_attempts=5,
        next_run_at=FIXED_NOW,
        started_at=FIXED_NOW - timedelta(minutes=1),
        failed_at=FIXED_NOW,
    )
    db_session.add(job)
    await db_session.commit()

    rejected = await auth_client.post(
        f"/api/v1/operator/jobs/{job.id}/retry",
        headers={"Idempotency-Key": "csrf-required"},
        json={"reason": "No CSRF must fail"},
    )
    assert rejected.status_code == 403
    assert rejected.json()["code"] == "CSRF_INVALID"

    paths = auth_app.openapi()["paths"]
    expected = {
        "/api/v1/organizations/{organization_id}/audit-events",
        "/api/v1/operator/jobs",
        "/api/v1/operator/jobs/{job_id}",
        "/api/v1/operator/jobs/{job_id}/retry",
        "/api/v1/operator/audit-events",
    }
    assert expected <= set(paths)
    assert set(paths["/api/v1/operator/jobs/{job_id}/retry"]) == {"post"}
    schemas = auth_app.openapi()["components"]["schemas"]
    assert {
        "payload",
        "idempotency_key",
        "locked_by",
    }.isdisjoint(schemas["OperatorJobDetail"]["properties"])
    assert "worker_id" not in schemas["OperatorJobAttemptResponse"]["properties"]
    assert "provider_message_id" not in schemas["OperatorEmailDeliveryResponse"]["properties"]


async def test_operator_routes_require_platform_access_and_completed_mfa(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user = make_user(email_normalized="operations-rbac@example.com")
    raw_session = "operations-rbac-session"
    session = Session(
        user=user,
        token_hash=hash_secret(raw_session),
        csrf_token_hash=hash_secret("operations-rbac-csrf"),
        last_seen_at=FIXED_NOW,
        absolute_expires_at=FIXED_NOW + timedelta(days=30),
    )
    db_session.add_all([user, session])
    await db_session.commit()
    auth_client.cookies.set("horeca_session", raw_session, path="/api/v1")

    ordinary = await auth_client.get("/api/v1/operator/jobs")
    assert ordinary.status_code == 403
    assert ordinary.json()["code"] == "FORBIDDEN"

    db_session.add(make_admin_access(user, scope="platform_operator"))
    await db_session.commit()
    missing_mfa = await auth_client.get("/api/v1/operator/jobs")
    assert missing_mfa.status_code == 403
    assert missing_mfa.json()["code"] == "MFA_REQUIRED"


async def test_concurrent_operator_retry_creates_one_requeued_job(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    _operator_id, csrf = await _arrange_elevated_session(
        auth_client,
        auth_app,
        db_session,
        scope="platform_operator",
    )
    job = BackgroundJob(
        job_type="attempt_expiry",
        status="failed",
        payload={"cutoff_at": FIXED_NOW.isoformat()},
        idempotency_key="attempt-expiry:concurrent-retry",
        attempt_count=5,
        max_attempts=5,
        next_run_at=FIXED_NOW,
        started_at=FIXED_NOW - timedelta(minutes=1),
        failed_at=FIXED_NOW,
    )
    db_session.add(job)
    await db_session.commit()
    headers = {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf,
        "Idempotency-Key": "concurrent-retry",
    }

    first, second = await asyncio.gather(
        auth_client.post(
            f"/api/v1/operator/jobs/{job.id}/retry",
            headers=headers,
            json={"reason": "One controlled retry"},
        ),
        auth_client.post(
            f"/api/v1/operator/jobs/{job.id}/retry",
            headers=headers,
            json={"reason": "One controlled retry"},
        ),
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["job"]["id"] == second.json()["job"]["id"]
    assert {first.json()["replayed"], second.json()["replayed"]} == {False, True}
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "operator.job.retried",
                AuditEvent.target_id == job.id,
            )
        )
        == 1
    )
