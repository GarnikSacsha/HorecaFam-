from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assessment,
    AttentionCase,
    Organization,
    Session,
)
from app.security.tokens import hash_secret
from tests.api.test_menu_admin_api import mutation_headers
from tests.factories.assessments import make_assessment
from tests.factories.auth import make_admin_access
from tests.integration.test_assessment_persistence import AssessmentContext, _make_context

FIXED_NOW = datetime(2031, 2, 3, 10, 0, tzinfo=UTC)


async def _arrange_admin_context(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    *,
    mfa_verified: bool = True,
) -> tuple[AssessmentContext, Assessment, UUID, str]:
    app.state.clock = lambda: FIXED_NOW
    context = await _make_context(db)
    organization = await db.get_one(Organization, context.training.organization_id)
    final_exam = make_assessment(
        context.training,
        None,
        assessment_type="menu_final_exam",
    )
    db.add_all(
        [
            final_exam,
            make_admin_access(
                context.actor,
                scope="organization_admin",
                organization=organization,
            ),
        ]
    )
    raw_session = f"attention-admin-session-{uuid4()}"
    csrf_token = f"attention-admin-csrf-{uuid4()}"
    db.add(
        Session(
            user_id=context.actor.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(csrf_token),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
            mfa_verified_at=FIXED_NOW if mfa_verified else None,
        )
    )
    await db.commit()
    client.cookies.set("horeca_session", raw_session, path="/api/v1")
    return context, final_exam, organization.id, csrf_token


async def test_admin_requirement_and_attention_lifecycles_are_protected_and_idempotent(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    context, final_exam, organization_id, csrf = await _arrange_admin_context(
        auth_client,
        auth_app,
        db_session,
    )
    case = AttentionCase(
        organization_id=organization_id,
        location_id=context.training.location_id,
        training_id=context.training.id,
        employee_profile_id=context.employee.id,
        case_type="critical_allergen",
        subject_key=f"menu_item:{uuid4()}:allergen:{uuid4()}",
        state="open",
        revision=0,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    db_session.add(case)
    await db_session.commit()

    base = f"/api/v1/organizations/{organization_id}"
    create_url = f"{base}/employees/{context.employee.id}/retake-requirements"
    payload = {
        "reason": "critical_error",
        "source_attention_case_id": str(case.id),
        "management_source_key": None,
        "target_policy": {
            "assessment_type": "menu_final_exam",
            "minimum_result": "passed",
            "required_subject_keys": [case.subject_key],
        },
        "due_at": (FIXED_NOW + timedelta(days=7)).isoformat(),
    }
    missing_csrf = await auth_client.post(
        create_url,
        headers={"Idempotency-Key": "proposal-missing-csrf"},
        json=payload,
    )
    created = await auth_client.post(
        create_url,
        headers=mutation_headers(csrf, key="proposal-create"),
        json=payload,
    )
    replay = await auth_client.post(
        create_url,
        headers=mutation_headers(csrf, key="proposal-create"),
        json=payload,
    )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_INVALID"
    assert created.status_code == 201, created.text
    assert replay.status_code == 201
    assert replay.json()["id"] == created.json()["id"]
    requirement_id = UUID(created.json()["id"])
    assert created.json()["state"] == "proposed"
    assert created.json()["timing_state"] is None
    assert created.json()["target_assessment_id"] == str(final_exam.id)

    edited_due = FIXED_NOW + timedelta(days=9)
    edited = await auth_client.patch(
        f"{base}/retake-requirements/{requirement_id}",
        headers=mutation_headers(csrf, key="proposal-edit"),
        json={"due_at": edited_due.isoformat(), "expected_revision": 0},
    )
    stale = await auth_client.patch(
        f"{base}/retake-requirements/{requirement_id}",
        headers=mutation_headers(csrf, key="proposal-stale"),
        json={"due_at": (edited_due + timedelta(days=1)).isoformat(), "expected_revision": 0},
    )
    confirmed = await auth_client.post(
        f"{base}/retake-requirements/{requirement_id}/confirm",
        headers=mutation_headers(csrf, key="proposal-confirm"),
        json={"expected_revision": 1},
    )
    active_edit = await auth_client.patch(
        f"{base}/retake-requirements/{requirement_id}",
        headers=mutation_headers(csrf, key="active-edit"),
        json={"due_at": (edited_due + timedelta(days=2)).isoformat(), "expected_revision": 2},
    )
    cancelled = await auth_client.post(
        f"{base}/retake-requirements/{requirement_id}/cancel",
        headers=mutation_headers(csrf, key="proposal-cancel"),
        json={"expected_revision": 2, "comment": "Follow-up replaced by direct coaching."},
    )

    assert edited.status_code == 200
    assert edited.json()["due_at"] == edited_due.isoformat().replace("+00:00", "Z")
    assert stale.status_code == 409
    assert stale.json()["code"] == "RETAKE_REQUIREMENT_CONFLICT"
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "active"
    assert active_edit.status_code == 409
    assert active_edit.json()["code"] == "RETAKE_REQUIREMENT_NOT_PROPOSED"
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"

    acknowledged = await auth_client.post(
        f"{base}/attention/{case.id}/acknowledge",
        headers=mutation_headers(csrf, key="attention-ack"),
        json={"expected_revision": 0},
    )
    resolved = await auth_client.post(
        f"{base}/attention/{case.id}/resolve",
        headers=mutation_headers(csrf, key="attention-resolve"),
        json={
            "expected_revision": 1,
            "resolution_type": "admin_follow_up",
            "comment": "Manager reviewed the allergen procedure with the employee.",
            "evidence_attempt_id": None,
        },
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["state"] == "acknowledged"
    assert resolved.status_code == 200
    assert resolved.json()["state"] == "resolved"
    assert resolved.json()["resolution_type"] == "admin_follow_up"

    listed = await auth_client.get(
        f"{base}/retake-requirements",
        params={"state": "cancelled", "reason": "critical_error", "limit": 1},
    )
    employee_requirements = await auth_client.get(
        f"{base}/retake-requirements",
        params={"q": str(context.employee.id)},
    )
    detail = await auth_client.get(f"{base}/retake-requirements/{requirement_id}")
    attention = await auth_client.get(f"{base}/attention", params={"state": "resolved"})
    employee_attention = await auth_client.get(f"{base}/employees/{context.employee.id}/attention")
    foreign = await auth_client.get(f"/api/v1/organizations/{uuid4()}/attention/{case.id}")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [str(requirement_id)]
    assert [item["id"] for item in employee_requirements.json()["items"]] == [str(requirement_id)]
    assert detail.status_code == 200
    assert attention.status_code == 200
    assert attention.json()["items"][0]["id"] == str(case.id)
    assert employee_attention.status_code == 200
    assert employee_attention.json()["items"][0]["id"] == str(case.id)
    assert foreign.status_code == 404


async def test_admin_attention_cursor_is_filter_bound_and_openapi_is_safe(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    context, _final_exam, organization_id, _csrf = await _arrange_admin_context(
        auth_client,
        auth_app,
        db_session,
    )
    for index in range(2):
        db_session.add(
            AttentionCase(
                organization_id=organization_id,
                location_id=context.training.location_id,
                training_id=context.training.id,
                employee_profile_id=context.employee.id,
                case_type="critical_allergen",
                subject_key=f"menu_item:{uuid4()}:allergen:{uuid4()}",
                state="open",
                revision=0,
                created_at=FIXED_NOW + timedelta(minutes=index),
                updated_at=FIXED_NOW + timedelta(minutes=index),
            )
        )
    await db_session.commit()
    base = f"/api/v1/organizations/{organization_id}/attention"
    first = await auth_client.get(base, params={"state": "open", "limit": 1})
    assert first.status_code == 200
    cursor = first.json()["next_cursor"]
    assert cursor
    second = await auth_client.get(
        base,
        params={"state": "open", "limit": 1, "cursor": cursor},
    )
    rebound = await auth_client.get(
        base,
        params={"state": "resolved", "limit": 1, "cursor": cursor},
    )
    assert second.status_code == 200
    assert second.json()["items"][0]["id"] != first.json()["items"][0]["id"]
    assert rebound.status_code == 422
    assert rebound.json()["code"] == "INVALID_CURSOR"

    openapi = auth_app.openapi()
    expected_paths = {
        "/api/v1/organizations/{organization_id}/retake-requirements",
        "/api/v1/organizations/{organization_id}/retake-requirements/{requirement_id}",
        "/api/v1/organizations/{organization_id}/employees/{employee_id}/retake-requirements",
        "/api/v1/organizations/{organization_id}/retake-requirements/{requirement_id}/confirm",
        "/api/v1/organizations/{organization_id}/retake-requirements/{requirement_id}/cancel",
        "/api/v1/organizations/{organization_id}/attention",
        "/api/v1/organizations/{organization_id}/attention/{attention_id}",
        "/api/v1/organizations/{organization_id}/employees/{employee_id}/attention",
        "/api/v1/organizations/{organization_id}/attention/{attention_id}/acknowledge",
        "/api/v1/organizations/{organization_id}/attention/{attention_id}/resolve",
    }
    assert expected_paths <= set(openapi["paths"])
    serialized = str(
        {
            name: openapi["components"]["schemas"][name]
            for name in ("AttentionCaseResponse", "RetakeRequirementResponse")
        }
    )
    for forbidden in (
        "grading_payload",
        "provenance_snapshot",
        "correct_option_ids",
        "source_fingerprint",
    ):
        assert forbidden not in serialized


async def test_admin_follow_up_requires_completed_mfa(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    _context, _final_exam, organization_id, _csrf = await _arrange_admin_context(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )
    response = await auth_client.get(f"/api/v1/organizations/{organization_id}/attention")
    assert response.status_code == 403
    assert response.json()["code"] == "MFA_REQUIRED"
