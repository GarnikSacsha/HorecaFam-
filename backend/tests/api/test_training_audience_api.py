from uuid import UUID

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BackgroundJob,
    EmployeeProfile,
    OperationalRole,
    Organization,
    TrainingAssignment,
    TrainingVersion,
    TrainingVersionAudience,
)
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu
from tests.factories.identity import make_membership, make_role, make_user


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
