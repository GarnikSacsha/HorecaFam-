import asyncio
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEvent,
    BackgroundJob,
    EmployeeProfile,
    Location,
    Organization,
    Training,
    TrainingAssignment,
    TrainingVersion,
)
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)
from tests.factories.training import make_training, make_training_assignment, make_training_version


async def arrange_assignment_context(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    *,
    mfa_verified: bool = True,
) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID, str]:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        client,
        app,
        db,
        mfa_verified=mfa_verified,
    )
    organization = await db.get(Organization, organization_id)
    assert organization is not None
    location = await db.get(Location, location_id)
    assert location is not None
    role = make_role(organization, code=f"assignment-role-{uuid4()}")
    employee_user = make_user(email_normalized=f"assignment-employee-{uuid4()}@example.com")
    membership = make_membership(organization, employee_user, activated_at=FIXED_NOW)
    employee = make_employee_profile(
        membership,
        organization_id,
        location_id=location.id,
        operational_role_id=role.id,
    )
    training = make_training(organization_id, location_id)
    version = make_training_version(
        training,
        admin_id,
        status="published",
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
    )
    db.add_all([role, employee_user, membership, employee, training, version])
    await db.commit()
    return (
        organization_id,
        location_id,
        admin_id,
        employee.id,
        training.id,
        version.id,
        csrf,
    )


async def test_admin_assignment_create_replays_and_records_safe_effects(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        location_id,
        admin_id,
        employee_id,
        training_id,
        version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    url = f"/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"
    headers = mutation_headers(csrf, key="assign-employee")

    created = await auth_client.post(
        url,
        headers=headers,
        json={"training_version_id": None, "reason": "Manual onboarding"},
    )
    replay = await auth_client.post(
        url,
        headers=headers,
        json={"training_version_id": None, "reason": "Manual onboarding"},
    )

    assert created.status_code == replay.status_code == 201, (created.json(), replay.json())
    assert replay.json() == created.json()
    expected_fields = {
        "organization_id": str(organization_id),
        "location_id": str(location_id),
        "employee_profile_id": str(employee_id),
        "training_id": str(training_id),
        "training_version_id": str(version_id),
        "status": "assigned",
        "source": "admin",
        "previous_assignment_id": None,
        "source_rollout_id": None,
        "started_at": None,
        "completed_at": None,
        "revoked_at": None,
        "revoke_reason": None,
        "revoke_note": None,
    }
    assert {key: created.json()[key] for key in expected_fields} == expected_fields
    assert await db_session.scalar(select(func.count()).select_from(TrainingAssignment)) == 1
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 1
    job = await db_session.scalar(select(BackgroundJob))
    assert job is not None
    assert job.payload == {
        "assignment_id": created.json()["id"],
        "template_code": "training_assigned",
        "locale": "uk",
    }
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "training_assignment_created")
    )
    assert audit is not None
    assert audit.actor_user_id == admin_id
    assert audit.new_values == {
        "employee_profile_id": str(employee_id),
        "training_id": str(training_id),
        "training_version_id": str(version_id),
        "source": "admin",
        "reason": "Manual onboarding",
    }


async def test_admin_assignment_revoke_and_reassign_preserve_lineage_and_history(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        admin_id,
        employee_id,
        training_id,
        version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    employee = await db_session.get(EmployeeProfile, employee_id)
    training = await db_session.get(Training, training_id)
    version = await db_session.get(TrainingVersion, version_id)
    assert employee is not None and training is not None and version is not None
    assignment = make_training_assignment(
        employee,
        training,
        version,
        source="admin",
        assigned_by_user_id=admin_id,
        assigned_at=FIXED_NOW,
    )
    db_session.add(assignment)
    await db_session.commit()
    base = (
        f"/api/v1/organizations/{organization_id}/employees/{employee_id}"
        f"/training-assignments/{assignment.id}"
    )

    revoked = await auth_client.post(
        f"{base}/revoke",
        headers=mutation_headers(csrf, key="revoke-assignment"),
        json={"reason": "Role exception"},
    )

    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["revoke_reason"] == "admin"
    assert revoked.json()["revoke_note"] == "Role exception"

    cannot_reassign_revoked = await auth_client.post(
        f"{base}/reassign",
        headers=mutation_headers(csrf, key="reassign-revoked"),
        json={"training_version_id": None, "reason": "Try invalid source"},
    )
    assert cannot_reassign_revoked.status_code == 409
    assert cannot_reassign_revoked.json()["code"] == "TRAINING_ASSIGNMENT_REVOKED"


async def test_admin_reassign_creates_new_current_assignment_without_mutating_source_version(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        admin_id,
        employee_id,
        training_id,
        version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    employee = await db_session.get(EmployeeProfile, employee_id)
    training = await db_session.get(Training, training_id)
    version = await db_session.get(TrainingVersion, version_id)
    assert employee is not None and training is not None and version is not None
    source = make_training_assignment(
        employee,
        training,
        version,
        source="admin",
        assigned_by_user_id=admin_id,
        assigned_at=FIXED_NOW,
    )
    db_session.add(source)
    await db_session.commit()
    url = (
        f"/api/v1/organizations/{organization_id}/employees/{employee_id}"
        f"/training-assignments/{source.id}/reassign"
    )

    reassigned = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="reassign-current"),
        json={"training_version_id": None, "reason": "Restart current training"},
    )
    replay = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="reassign-current"),
        json={"training_version_id": None, "reason": "Restart current training"},
    )

    assert reassigned.status_code == replay.status_code == 200, (
        reassigned.json(),
        replay.json(),
    )
    assert replay.json() == reassigned.json()
    assert reassigned.json()["id"] != str(source.id)
    assert reassigned.json()["training_version_id"] == str(version_id)
    assert reassigned.json()["previous_assignment_id"] == str(source.id)
    assert reassigned.json()["source"] == "reassign"
    await db_session.refresh(source)
    assert source.status == "revoked"
    assert source.training_version_id == version_id
    assert source.revoke_reason == "admin"
    listed = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"
    )
    assert listed.status_code == 200
    assert listed.json()["current"]["id"] == reassigned.json()["id"]
    assert [row["id"] for row in listed.json()["history"]] == [str(source.id)]
    assert listed.json()["progress"] == {
        "required_lesson_count": 0,
        "completed_required_lesson_count": 0,
        "percentage": 0,
        "is_complete": False,
    }


async def test_admin_assignment_rejects_duplicate_and_foreign_scope_without_leakage(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        admin_id,
        employee_id,
        training_id,
        version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    employee = await db_session.get(EmployeeProfile, employee_id)
    training = await db_session.get(Training, training_id)
    version = await db_session.get(TrainingVersion, version_id)
    assert employee is not None and training is not None and version is not None
    db_session.add(
        make_training_assignment(
            employee,
            training,
            version,
            source="admin",
            assigned_by_user_id=admin_id,
        )
    )
    foreign = make_organization(name="Foreign")
    foreign_location = make_location(foreign)
    db_session.add_all([foreign, foreign_location])
    await db_session.flush()
    foreign_training = make_training(foreign.id, foreign_location.id)
    db_session.add(foreign_training)
    await db_session.flush()
    foreign_version = make_training_version(
        foreign_training,
        admin_id,
        status="published",
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
    )
    db_session.add(foreign_version)
    await db_session.commit()
    url = f"/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"

    duplicate = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="duplicate-assignment"),
        json={"training_version_id": str(version_id), "reason": None},
    )
    foreign_read = await auth_client.get(
        f"/api/v1/organizations/{foreign.id}/employees/{employee_id}/training-assignments"
    )
    foreign_version_probe = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="foreign-version-assignment"),
        json={"training_version_id": str(foreign_version.id), "reason": None},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "TRAINING_ASSIGNMENT_EXISTS"
    assert foreign_read.status_code == 404
    assert foreign_read.json()["code"] == "RESOURCE_NOT_FOUND"
    assert foreign_version_probe.status_code == 404
    assert foreign_version_probe.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_admin_assignment_security_and_idempotency_key_reuse(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        _admin_id,
        employee_id,
        _training_id,
        version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    url = f"/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"

    missing_csrf = await auth_client.post(
        url,
        headers={"Origin": "https://frontend.test", "Idempotency-Key": "missing-csrf"},
        json={"training_version_id": None, "reason": None},
    )
    created = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="assignment-reused-key"),
        json={"training_version_id": None, "reason": "First reason"},
    )
    changed_replay = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="assignment-reused-key"),
        json={"training_version_id": str(version_id), "reason": "Changed reason"},
    )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_INVALID"
    assert created.status_code == 201
    assert changed_replay.status_code == 409
    assert changed_replay.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_admin_assignment_read_requires_completed_mfa(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        _admin_id,
        employee_id,
        _training_id,
        _version_id,
        _csrf,
    ) = await arrange_assignment_context(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )

    response = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"
    )

    assert response.status_code == 403
    assert response.json()["code"] == "MFA_REQUIRED"


async def test_admin_reassign_accepts_explicit_retained_version(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        admin_id,
        employee_id,
        training_id,
        version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    employee = await db_session.get(EmployeeProfile, employee_id)
    training = await db_session.get(Training, training_id)
    current_version = await db_session.get(TrainingVersion, version_id)
    assert employee is not None and training is not None and current_version is not None
    retained_version = make_training_version(
        training,
        admin_id,
        version_number=2,
        status="archived",
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
        archived_at=FIXED_NOW,
    )
    source = make_training_assignment(
        employee,
        training,
        current_version,
        source="admin",
        assigned_by_user_id=admin_id,
    )
    db_session.add_all([retained_version, source])
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/employees/{employee_id}"
        f"/training-assignments/{source.id}/reassign",
        headers=mutation_headers(csrf, key="reassign-retained"),
        json={"training_version_id": str(retained_version.id), "reason": None},
    )

    assert response.status_code == 200
    assert response.json()["training_version_id"] == str(retained_version.id)
    assert response.json()["previous_assignment_id"] == str(source.id)


async def test_admin_assignment_openapi_exposes_exact_lifecycle_without_assessment_fields(
    auth_app: FastAPI,
) -> None:
    schema = auth_app.openapi()
    base = "/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"
    assignment = f"{base}/{{assignment_id}}"

    assert set(schema["paths"][base]) == {"get", "post"}
    assert set(schema["paths"][f"{assignment}/revoke"]) == {"post"}
    assert set(schema["paths"][f"{assignment}/reassign"]) == {"post"}
    assert "201" in schema["paths"][base]["post"]["responses"]
    for operation in (
        schema["paths"][base]["post"],
        schema["paths"][f"{assignment}/revoke"]["post"],
        schema["paths"][f"{assignment}/reassign"]["post"],
    ):
        idempotency = next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "Idempotency-Key"
        )
        assert idempotency["required"] is True
        assert idempotency["in"] == "header"
    serialized = str(
        {
            name: value
            for name, value in schema["components"]["schemas"].items()
            if name.startswith("TrainingAssignment") or name == "TrainingProgressResponse"
        }
    ).lower()
    assert "correct_answer" not in serialized
    assert "answer_key" not in serialized
    assert "certification" not in serialized
    assert "score" not in serialized


async def test_concurrent_different_keys_leave_only_one_current_assignment(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        _location_id,
        _admin_id,
        employee_id,
        _training_id,
        _version_id,
        csrf,
    ) = await arrange_assignment_context(auth_client, auth_app, db_session)
    url = f"/api/v1/organizations/{organization_id}/employees/{employee_id}/training-assignments"

    first, second = await asyncio.gather(
        auth_client.post(
            url,
            headers=mutation_headers(csrf, key="concurrent-assignment-one"),
            json={"training_version_id": None, "reason": None},
        ),
        auth_client.post(
            url,
            headers=mutation_headers(csrf, key="concurrent-assignment-two"),
            json={"training_version_id": None, "reason": None},
        ),
    )

    assert sorted(response.status_code for response in (first, second)) == [201, 409], (
        first.json(),
        second.json(),
    )
    conflict = next(response for response in (first, second) if response.status_code == 409)
    assert conflict.json()["code"] == "TRAINING_ASSIGNMENT_EXISTS"
    current_count = await db_session.scalar(
        select(func.count())
        .select_from(TrainingAssignment)
        .where(TrainingAssignment.status != "revoked")
    )
    assert current_count == 1
