import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assessment,
    AttentionCase,
    AttentionCaseAction,
    Organization,
    RetakeRequirement,
    RetakeRequirementAction,
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


@pytest.mark.parametrize("damage", ["encoding", "shape", "id", "date", "naive_date", "naive_empty"])
@pytest.mark.parametrize("resource", ["attention", "retake-requirements"])
async def test_attention_rejects_malformed_cursor_with_controlled_error(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    damage: str,
    resource: str,
) -> None:
    context, final_exam, organization_id, _ = await _arrange_admin_context(
        auth_client, auth_app, db_session
    )
    cases = [
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
        for index in range(2)
    ]
    db_session.add_all(cases)
    db_session.add_all(
        [
            RetakeRequirement(
                organization_id=organization_id,
                location_id=context.training.location_id,
                training_id=context.training.id,
                employee_profile_id=context.employee.id,
                assignment_id=context.assignment.id,
                target_assessment_id=final_exam.id,
                reason="management_follow_up",
                state="active",
                management_source_key=f"cursor-check-{index}",
                target_policy={"assessment_type": "menu_final_exam", "minimum_result": "passed"},
                confirmed_at=FIXED_NOW,
                confirmed_by_user_id=context.actor.id,
                due_at=FIXED_NOW + timedelta(days=7, minutes=index),
                revision=0,
            )
            for index in range(2)
        ]
    )
    await db_session.commit()
    base = f"/api/v1/organizations/{organization_id}/{resource}"
    first = await auth_client.get(base, params={"limit": 1})
    assert first.status_code == 200
    cursor = first.json()["next_cursor"]
    assert isinstance(cursor, str)
    second = await auth_client.get(base, params={"limit": 1, "cursor": cursor})
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1 and second.json()["next_cursor"] is None
    assert second.json()["items"][0]["id"] != first.json()["items"][0]["id"]
    if damage == "naive_empty":
        model = AttentionCase if resource == "attention" else RetakeRequirement
        await db_session.execute(delete(model).where(model.organization_id == organization_id))
        await db_session.commit()
        first = await auth_client.get(base, params={"limit": 1})
        assert first.status_code == 200 and first.json()["items"] == []
    decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    if damage == "encoding":
        damaged = "not-a-json-cursor"
    else:
        if damage == "shape":
            decoded["k"] = []
        elif damage == "id":
            decoded["k"][2] = "not-a-uuid"
        elif damage == "date":
            decoded["k"][1] = "not-a-date"
        else:
            decoded["k"][1] = "2031-02-03T10:00:00"
        damaged = base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode().rstrip("=")
    async with AsyncClient(
        transport=ASGITransport(app=auth_app, raise_app_exceptions=False),
        base_url="https://api.test",
        cookies=auth_client.cookies,
    ) as client:
        rejected = await client.get(base, params={"limit": 1, "cursor": damaged})
    after = await auth_client.get(base, params={"limit": 1})
    assert after.status_code == 200 and after.json() == first.json()
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "INVALID_CURSOR"


async def test_management_requirement_rejections_preserve_obligation_and_actions(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    context, _, organization_id, csrf = await _arrange_admin_context(
        auth_client, auth_app, db_session
    )
    base = f"/api/v1/organizations/{organization_id}"
    created = await auth_client.post(
        f"{base}/employees/{context.employee.id}/retake-requirements",
        headers=mutation_headers(csrf, key="management-proposal"),
        json={
            "reason": "management_follow_up",
            "management_source_key": "manager-check",
            "target_policy": {"assessment_type": "menu_final_exam", "minimum_result": "passed"},
        },
    )
    assert created.status_code == 201
    requirement_id = created.json()["id"]
    url = f"{base}/retake-requirements/{requirement_id}"
    due = (FIXED_NOW + timedelta(days=7)).isoformat()
    cases: list[tuple[str, str, dict[str, object], int, str]] = [
        (
            "PATCH",
            url,
            {"expected_revision": 99, "due_at": due},
            409,
            "RETAKE_REQUIREMENT_CONFLICT",
        ),
        ("POST", f"{url}/confirm", {"expected_revision": 99}, 409, "RETAKE_REQUIREMENT_CONFLICT"),
        (
            "POST",
            f"{url}/cancel",
            {"expected_revision": 99, "comment": "Reviewed"},
            409,
            "RETAKE_REQUIREMENT_CONFLICT",
        ),
        (
            "PATCH",
            url,
            {"expected_revision": 0, "due_at": "2031-02-10T10:00:00"},
            422,
            "RETAKE_DUE_AT_INVALID",
        ),
    ]
    unknown = f"{base}/retake-requirements/{uuid4()}"
    cases.extend(
        [
            (
                "PATCH",
                unknown,
                {"expected_revision": 0, "due_at": due},
                404,
                "RETAKE_REQUIREMENT_NOT_FOUND",
            ),
            (
                "POST",
                f"{unknown}/confirm",
                {"expected_revision": 0},
                404,
                "RETAKE_REQUIREMENT_NOT_FOUND",
            ),
            (
                "POST",
                f"{unknown}/cancel",
                {"expected_revision": 0, "comment": "Reviewed"},
                404,
                "RETAKE_REQUIREMENT_NOT_FOUND",
            ),
        ]
    )
    before = await auth_client.get(url)
    action_count = await db_session.scalar(
        select(func.count()).select_from(RetakeRequirementAction)
    )
    for index, (method, target, payload, status, code) in enumerate(cases):
        denied = await auth_client.request(
            method, target, headers=mutation_headers(csrf, key=f"denied-{index}"), json=payload
        )
        assert denied.status_code == status, (index, denied.status_code)
        assert denied.json()["code"] == code
        after = await auth_client.get(url)
        assert after.json() == before.json()
        assert (
            await db_session.scalar(select(func.count()).select_from(RetakeRequirementAction))
            == action_count
        )
    elapsed = await auth_client.patch(
        url,
        headers=mutation_headers(csrf, key="past-proposal"),
        json={"expected_revision": 0, "due_at": FIXED_NOW.isoformat()},
    )
    assert elapsed.status_code == 200 and elapsed.json()["revision"] == 1
    rejected = await auth_client.post(
        f"{url}/confirm",
        headers=mutation_headers(csrf, key="due-boundary"),
        json={"expected_revision": 1},
    )
    assert rejected.status_code == 422 and rejected.json()["code"] == "RETAKE_DUE_AT_INVALID"
    future = await auth_client.patch(
        url,
        headers=mutation_headers(csrf, key="future-proposal"),
        json={"expected_revision": 1, "due_at": due},
    )
    assert future.status_code == 200 and future.json()["revision"] == 2
    active = await auth_client.post(
        f"{url}/confirm",
        headers=mutation_headers(csrf, key="confirm-future"),
        json={"expected_revision": 2},
    )
    assert active.status_code == 200 and active.json()["state"] == "active"
    employee_name = context.employee.first_name
    assert employee_name is not None
    positive_filters: list[dict[str, str]] = [
        {"state": "active"},
        {"reason": "management_follow_up"},
        {"timing_state": "scheduled"},
        {"location_id": str(context.training.location_id)},
        {"q": employee_name},
        {"q": str(context.employee.id)},
    ]
    for filters in positive_filters:
        response = await auth_client.get(f"{base}/retake-requirements", params=filters)
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [requirement_id]
    for filters in ({"location_id": str(uuid4())}, {"q": "%_"}, {"timing_state": "overdue"}):
        response = await auth_client.get(f"{base}/retake-requirements", params=filters)
        assert response.status_code == 200 and response.json()["items"] == []
    blank = await auth_client.get(f"{base}/retake-requirements", params={"q": "  "})
    assert blank.status_code == 422 and blank.json()["code"] == "VALIDATION_ERROR"
    active_rejections: list[tuple[str, str, dict[str, object]]] = [
        ("PATCH", url, {"expected_revision": 3, "due_at": due}),
        ("POST", f"{url}/confirm", {"expected_revision": 3}),
    ]
    for method, target, payload in active_rejections:
        denied = await auth_client.request(
            method, target, headers=mutation_headers(csrf, key=str(uuid4())), json=payload
        )
        assert (
            denied.status_code == 409 and denied.json()["code"] == "RETAKE_REQUIREMENT_NOT_PROPOSED"
        )
    cancelled = await auth_client.post(
        f"{url}/cancel",
        headers=mutation_headers(csrf, key="cancel-active"),
        json={"expected_revision": 3, "comment": "Reviewed cancellation"},
    )
    assert cancelled.status_code == 200 and cancelled.json()["state"] == "cancelled"
    action_count = await db_session.scalar(
        select(func.count()).select_from(RetakeRequirementAction)
    )
    repeated = await auth_client.post(
        f"{url}/cancel",
        headers=mutation_headers(csrf, key="cancel-again"),
        json={"expected_revision": 3, "comment": "Reviewed cancellation"},
    )
    assert repeated.status_code == 200 and repeated.json() == cancelled.json()
    assert (
        await db_session.scalar(select(func.count()).select_from(RetakeRequirementAction))
        == action_count
    )


async def test_attention_filters_and_resolution_guards_preserve_case_history(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    context, _, org_id, csrf = await _arrange_admin_context(auth_client, auth_app, db_session)
    case = AttentionCase(
        organization_id=org_id,
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
    base = f"/api/v1/organizations/{org_id}"
    name = context.employee.first_name
    assert name is not None
    for filters in [
        {"state": "open"},
        {"type": "critical_allergen"},
        {"severity": "critical"},
        {"location_id": str(context.training.location_id)},
        {"q": name},
    ]:
        response = await auth_client.get(f"{base}/attention", params=filters)
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [str(case.id)]
    for filters in [{"severity": "overdue"}, {"q": "%_"}, {"location_id": str(uuid4())}]:
        response = await auth_client.get(f"{base}/attention", params=filters)
        assert response.status_code == 200 and response.json()["items"] == []
    blank = await auth_client.get(f"{base}/attention", params={"q": "   "})
    assert blank.status_code == 422 and blank.json()["code"] == "VALIDATION_ERROR"
    own = await auth_client.get(f"{base}/employees/{context.employee.id}/attention")
    assert own.status_code == 200 and own.json()["items"][0]["id"] == str(case.id)
    for path in [f"{base}/employees/{uuid4()}/attention", f"{base}/attention/{uuid4()}"]:
        missing = await auth_client.get(path)
        assert missing.status_code == 404 and missing.json()["code"] == "ATTENTION_CASE_NOT_FOUND"
    url = f"{base}/attention/{case.id}"
    original = await auth_client.get(url)
    count = await db_session.scalar(select(func.count()).select_from(AttentionCaseAction))
    cases: list[tuple[str, dict[str, object], int, str]] = [
        ("acknowledge", {"expected_revision": 99}, 409, "RETAKE_REQUIREMENT_CONFLICT"),
        (
            "resolve",
            {"expected_revision": 99, "resolution_type": "admin_follow_up", "comment": "Reviewed"},
            409,
            "RETAKE_REQUIREMENT_CONFLICT",
        ),
        (
            "resolve",
            {"expected_revision": 0, "resolution_type": "admin_follow_up"},
            422,
            "ATTENTION_RESOLUTION_INVALID",
        ),
        (
            "resolve",
            {
                "expected_revision": 0,
                "resolution_type": "clean_retake",
                "evidence_attempt_id": str(uuid4()),
            },
            422,
            "CLEAN_RETAKE_NOT_PROVEN",
        ),
    ]
    for index, (action, payload, status, code) in enumerate(cases):
        denied = await auth_client.post(
            f"{url}/{action}",
            headers=mutation_headers(csrf, key=f"case-denied-{index}"),
            json=payload,
        )
        assert denied.status_code == status and denied.json()["code"] == code
        current = await auth_client.get(url)
        assert current.json() == original.json()
        assert (
            await db_session.scalar(select(func.count()).select_from(AttentionCaseAction)) == count
        )
    resolved = await auth_client.post(
        f"{url}/resolve",
        headers=mutation_headers(csrf, key="case-resolve"),
        json={"expected_revision": 0, "resolution_type": "admin_follow_up", "comment": "Reviewed"},
    )
    assert resolved.status_code == 200 and resolved.json()["state"] == "resolved"
    count = await db_session.scalar(select(func.count()).select_from(AttentionCaseAction))
    terminal_rejections: list[tuple[str, dict[str, object]]] = [
        ("acknowledge", {"expected_revision": 1}),
        (
            "resolve",
            {"expected_revision": 1, "resolution_type": "admin_follow_up", "comment": "Reviewed"},
        ),
    ]
    for action, payload in terminal_rejections:
        denied = await auth_client.post(
            f"{url}/{action}",
            headers=mutation_headers(csrf, key=f"terminal-{action}"),
            json=payload,
        )
        assert (
            denied.status_code == 409 and denied.json()["code"] == "ATTENTION_CASE_ALREADY_RESOLVED"
        )
        assert (
            await db_session.scalar(select(func.count()).select_from(AttentionCaseAction)) == count
        )
