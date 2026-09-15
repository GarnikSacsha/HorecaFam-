from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminAccess,
    AuditEvent,
    BackgroundJob,
    EmployeeProfile,
    OperationalRole,
    Organization,
    Session,
    TrainingAssignment,
    TrainingVersion,
    TrainingVersionAudience,
    User,
)
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu
from tests.factories.identity import make_membership, make_role, make_user


@pytest.mark.parametrize("version_status", ["draft", "published", "archived"])
async def test_audience_read_keeps_complete_set_and_does_not_mutate(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    version_status: str,
) -> None:
    org_id, location_id, _admin_id, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org_id}/locations/{location_id}/training-versions"
    created = await auth_client.post(
        base,
        headers=mutation_headers(csrf, key="read-audience"),
        json={"base_version_id": None},
    )
    assert created.status_code == 201
    version_id = UUID(created.json()["id"])
    organization = await db_session.get_one(Organization, org_id)
    roles = [make_role(organization, code=f"role-{uuid4()}") for _ in range(2)]
    db_session.add_all(roles)
    await db_session.commit()
    saved = await auth_client.put(
        f"{base}/{version_id}/audiences",
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "operational_role_ids": [str(role.id) for role in roles]},
    )
    assert saved.status_code == 200
    roles[0].status = "archived"
    version = await db_session.get_one(TrainingVersion, version_id)
    version.status = version_status
    if version_status != "draft":
        version.published_at = FIXED_NOW
        version.published_by_user_id = _admin_id
    if version_status == "archived":
        version.archived_at = FIXED_NOW
    await db_session.commit()
    before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = await auth_client.get(f"{base}/{version_id}/audiences")
    assert response.status_code == 200
    assert response.json() == saved.json()
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
    await db_session.refresh(version)
    assert version.revision == 1
    assert await db_session.scalar(select(func.count()).select_from(TrainingVersionAudience)) == 2
    for path in [
        f"{base}/{uuid4()}/audiences",
        f"/api/v1/organizations/{org_id}/locations/{uuid4()}/training-versions/{version_id}/audiences",
        f"/api/v1/organizations/{uuid4()}/locations/{location_id}/training-versions/{version_id}/audiences",
    ]:
        missing = await auth_client.get(path)
        assert missing.status_code == 404
        assert missing.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_audience_read_requires_admin_mfa_and_session(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    path = (
        "/api/v1/organizations/{organization_id}/locations/{location_id}/"
        "training-versions/{version_id}/audiences"
    )
    operation = auth_app.openapi()["paths"][path]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TrainingAudienceResponse",
    }
    assert "requestBody" not in operation
    org_id, location_id, admin_id, _csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )
    url = (
        f"/api/v1/organizations/{org_id}/locations/{location_id}/"
        f"training-versions/{uuid4()}/audiences"
    )
    denied = await auth_client.get(url)
    assert denied.status_code == 403
    assert denied.json()["code"] == "MFA_REQUIRED"
    session = await db_session.scalar(select(Session).where(Session.user_id == admin_id))
    assert session is not None
    session.mfa_verified_at = FIXED_NOW
    access = await db_session.scalar(select(AdminAccess).where(AdminAccess.user_id == admin_id))
    assert access is not None
    access.status = "revoked"
    access.revoked_at = FIXED_NOW
    organization = await db_session.get_one(Organization, org_id)
    user = await db_session.get_one(User, admin_id)
    db_session.add(make_membership(organization, user, status="active", activated_at=FIXED_NOW))
    await db_session.commit()
    denied = await auth_client.get(url)
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"
    auth_client.cookies.clear()
    anonymous = await auth_client.get(url)
    assert anonymous.status_code == 401


async def test_training_audience_update_is_draft_only_revision_safe_and_exact(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    role = make_role(await db_session.get_one(Organization, organization_id))
    db_session.add(role)
    await db_session.commit()
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    draft = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="audience-draft"),
        json={"base_version_id": None},
    )
    assert draft.status_code == 201
    version_id = UUID(draft.json()["id"])
    audience_url = f"{versions_url}/{version_id}/audiences"

    empty = await auth_client.get(audience_url)
    assert empty.status_code == 200
    assert empty.json() == {
        "training_version_id": str(version_id),
        "revision": 0,
        "operational_role_ids": [],
    }

    updated = await auth_client.put(
        audience_url,
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "operational_role_ids": [str(role.id)]},
    )
    stale = await auth_client.put(
        audience_url,
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "operational_role_ids": [str(role.id)]},
    )

    assert updated.status_code == 200
    assert updated.json() == {
        "training_version_id": str(version_id),
        "revision": 1,
        "operational_role_ids": [str(role.id)],
    }
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"
    current = await auth_client.get(audience_url)
    assert current.status_code == 200
    assert current.json() == updated.json()
    assert (await db_session.get_one(TrainingVersion, version_id)).revision == 1
    assert (
        list(
            (
                await db_session.scalars(
                    select(TrainingVersionAudience).where(
                        TrainingVersionAudience.training_version_id == version_id
                    )
                )
            ).all()
        )[0].operational_role_id
        == role.id
    )


async def test_first_training_publish_assigns_each_applicable_active_employee_once(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    organization = await db_session.get_one(Organization, organization_id)
    role = await db_session.scalar(
        select(OperationalRole).where(OperationalRole.organization_id == organization_id)
    )
    assert role is not None
    user = make_user(email_normalized="applicable-publish@example.com")
    membership = make_membership(
        organization,
        user,
        status="active",
        activated_at=FIXED_NOW,
    )
    db_session.add_all([user, membership])
    await db_session.flush()
    db_session.add(
        EmployeeProfile(
            membership_id=membership.id,
            organization_id=organization_id,
            first_name="Марія",
            last_name="Коваль",
            operational_role_id=role.id,
            location_id=location_id,
        )
    )
    await db_session.commit()
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="applicable-publish-menu",
    )
    draft = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="applicable-publish-training",
    )
    version_id = UUID(str(draft["id"]))
    url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-versions/{version_id}/publish"
    )
    headers = mutation_headers(csrf, key="applicable-first-publish")
    payload = {"expected_revision": draft["revision"]}
    response = await auth_client.post(url, headers=headers, json=payload)
    replay = await auth_client.post(url, headers=headers, json=payload)

    assert response.status_code == replay.status_code == 200
    assert response.json() == replay.json()
    assert response.json()["assignment_count"] == 1
    assert response.json()["notification_count"] == 1
    assert await db_session.scalar(select(func.count()).select_from(TrainingAssignment)) == 1
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(BackgroundJob.job_type == "training_assignment_notification")
        )
        == 1
    )
