from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationalRole, Organization, Session, TrainingVersion
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.factories.identity import make_organization, make_role


async def test_admin_creates_multiple_service_modules_without_replacing_menu(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    draft = await auth_client.post(
        base,
        headers=mutation_headers(csrf, key="position-draft"),
        json={"base_version_id": None},
    )
    assert draft.status_code == 201
    version_id = draft.json()["id"]
    menu_id = draft.json()["modules"][0]["id"]
    module_ids = []
    for revision, title in enumerate(("Робота ранера", "Стандарти сервісу")):
        response = await auth_client.post(
            f"{base}/{version_id}/modules",
            headers=mutation_headers(csrf),
            json={
                "expected_revision": revision,
                "domain_type": "service",
                "title_uk": title,
                "description_uk": None,
                "required": True,
                "all_positions": True,
                "operational_role_ids": [],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["revision"] == revision + 1
        assert data["module"]["domain_type"] == "service"
        assert data["module"]["all_positions"] is True
        module_ids.append(data["module"]["id"])

    detail = await auth_client.get(f"{base}/{version_id}")
    assert detail.status_code == 200
    modules = detail.json()["modules"]
    assert [row["id"] for row in modules] == [menu_id, *module_ids]
    assert len(set(row["id"] for row in modules)) == 3
    assert modules[0]["domain_type"] == "menu"
    readiness = await auth_client.get(f"{base}/{version_id}/readiness")
    assert readiness.status_code == 200
    blocked_modules = {
        issue["entity_id"]
        for issue in readiness.json()["blocking_errors"]
        if issue["code"] == "REQUIRED_LESSON_MISSING" and issue["entity_type"] == "training_module"
    }
    assert set(module_ids) <= blocked_modules


async def test_training_audience_supports_all_current_and_future_positions(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    draft = await auth_client.post(
        base,
        headers=mutation_headers(csrf, key="all-positions-draft"),
        json={"base_version_id": None},
    )
    assert draft.status_code == 201
    url = f"{base}/{draft.json()['id']}/audiences"
    saved = await auth_client.put(
        url,
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "all_positions": True, "operational_role_ids": []},
    )
    assert saved.status_code == 200
    assert saved.json()["all_positions"] is True
    assert saved.json()["operational_role_ids"] == []
    assert (await auth_client.get(url)).json() == saved.json()


@pytest.mark.parametrize("operation", ["create", "audience"])
@pytest.mark.parametrize(
    "guard,expected",
    [
        ("csrf", 403),
        ("mfa", 403),
        ("scope", 404),
        ("published", 409),
        ("revision", 409),
        ("foreign_role", 404),
        ("mixed", 422),
        ("empty", 422),
    ],
)
async def test_module_mutations_preserve_authorization_and_draft_boundaries(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    operation: str,
    guard: str,
    expected: int,
) -> None:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    draft = await auth_client.post(
        base,
        headers=mutation_headers(csrf, key="module-guards"),
        json={"base_version_id": None},
    )
    assert draft.status_code == 201
    version_id = UUID(draft.json()["id"])
    module_id = draft.json()["modules"][0]["id"]
    payload: dict[str, object] = {
        "expected_revision": 0,
        "all_positions": True,
        "operational_role_ids": [],
    }
    headers = mutation_headers(csrf)
    if guard == "csrf":
        headers = {}
    elif guard == "mfa":
        session = await db_session.scalar(select(Session).where(Session.user_id == admin_id))
        assert session is not None
        session.mfa_verified_at = None
    elif guard == "scope":
        base = base.replace(str(location_id), str(uuid4()))
    elif guard == "published":
        version = await db_session.get_one(TrainingVersion, version_id)
        version.status = "published"
        version.published_by_user_id = admin_id
        version.published_at = FIXED_NOW
    elif guard == "revision":
        payload["expected_revision"] = 1
    elif guard == "foreign_role":
        foreign_organization = make_organization(name="Another tenant")
        foreign_role = make_role(foreign_organization)
        db_session.add_all([foreign_organization, foreign_role])
        await db_session.flush()
        payload.update(all_positions=False, operational_role_ids=[str(foreign_role.id)])
    elif guard == "mixed":
        payload["operational_role_ids"] = [str(uuid4())]
    elif guard == "empty":
        payload["all_positions"] = False
    await db_session.commit()
    if operation == "create":
        payload.update(domain_type="service", title_uk="Новий модуль", required=True)
        response = await auth_client.post(
            f"{base}/{version_id}/modules",
            headers=headers,
            json=payload,
        )
    else:
        response = await auth_client.put(
            f"{base}/{version_id}/modules/{module_id}/audience",
            headers=headers,
            json=payload,
        )
    assert response.status_code == expected
    version = await db_session.get_one(TrainingVersion, version_id)
    await db_session.refresh(version)
    assert version.revision == 0


async def test_module_audience_replaces_one_multiple_and_all_positions_exactly(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    organization = await db_session.get_one(Organization, organization_id)
    db_session.add(make_role(organization, code="runner", name_uk="Ранер"))
    await db_session.commit()
    role_ids = sorted(
        str(role_id)
        for role_id in (
            await db_session.scalars(
                select(OperationalRole.id).where(OperationalRole.organization_id == organization_id)
            )
        ).all()
    )
    assert len(role_ids) >= 2
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    draft = await auth_client.post(
        base, headers=mutation_headers(csrf, key="replace-module"), json={"base_version_id": None}
    )
    assert draft.status_code == 201
    version_id = draft.json()["id"]
    module_id = draft.json()["modules"][0]["id"]
    for revision, selected in enumerate((role_ids, role_ids[:1], [])):
        response = await auth_client.put(
            f"{base}/{version_id}/modules/{module_id}/audience",
            headers=mutation_headers(csrf),
            json={
                "expected_revision": revision,
                "all_positions": not selected,
                "operational_role_ids": selected,
            },
        )
        assert response.status_code == 200
        assert response.json()["revision"] == revision + 1
        assert response.json()["module"]["operational_role_ids"] == selected
        assert response.json()["module"]["all_positions"] is (not selected)
        detail = await auth_client.get(f"{base}/{version_id}")
        assert detail.json()["modules"][0] == response.json()["module"]
