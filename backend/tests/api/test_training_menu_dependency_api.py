import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminAccess,
    AuditEvent,
    MenuItemVersion,
    MenuVersion,
    Organization,
    Session,
    TrainingVersion,
    TrainingVersionMenuDependency,
)
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.api.test_training_publication_api import publish_menu
from tests.factories.identity import make_location, make_organization
from tests.factories.menu import make_menu, make_menu_version
from tests.factories.training import make_training, make_training_version


async def test_draft_created_before_menu_can_recover_dependency(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}"
    created = await auth_client.post(
        f"{base}/training-versions",
        headers=mutation_headers(csrf, key="dependency-draft"),
        json={"base_version_id": None},
    )
    assert created.status_code == 201
    draft = created.json()
    assert draft["menu_version_id"] is None
    version_url = f"{base}/training-versions/{draft['id']}"
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="dependency-menu",
    )
    menu = await db_session.scalar(select(MenuVersion).where(MenuVersion.status == "published"))
    assert menu is not None
    before = await auth_client.get(f"{version_url}/readiness")
    assert "MENU_DEPENDENCY_INVALID" in {item["code"] for item in before.json()["blocking_errors"]}
    assert (await auth_client.get(version_url)).json()["menu_version_id"] is None
    recovered = await auth_client.put(
        f"{version_url}/menu-dependency",
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "menu_version_id": str(menu.id)},
    )
    assert recovered.status_code == 200
    assert recovered.json()["menu_version_id"] == str(menu.id)
    assert recovered.json()["revision"] == 1
    after = await auth_client.get(f"{version_url}/readiness")
    assert "MENU_DEPENDENCY_INVALID" not in {
        item["code"] for item in after.json()["blocking_errors"]
    }
    dependency = await db_session.scalar(
        select(TrainingVersionMenuDependency).where(
            TrainingVersionMenuDependency.training_version_id == UUID(draft["id"])
        )
    )
    assert dependency is not None and dependency.menu_version_id == menu.id
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "training_menu_dependency_bound")
    )
    assert audit is not None and audit.target_id == UUID(draft["id"])
    lesson = await auth_client.post(
        f"{version_url}/modules/{draft['modules'][0]['id']}/lessons",
        headers=mutation_headers(csrf),
        json={"expected_revision": 1, "title_uk": "Меню", "required": True},
    )
    assert lesson.status_code == 200
    item = await db_session.scalar(
        select(MenuItemVersion).where(MenuItemVersion.menu_version_id == menu.id)
    )
    assert item is not None
    card = await auth_client.post(
        f"{version_url}/lessons/{lesson.json()['lesson']['id']}/content-blocks",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 2,
            "type": "menu_item_card",
            "payload": {"menu_item_id": str(item.menu_item_id)},
        },
    )
    assert card.status_code == 200
    roles = await auth_client.get(f"/api/v1/organizations/{organization_id}/operational-roles")
    audience = await auth_client.put(
        f"{version_url}/audiences",
        headers=mutation_headers(csrf),
        json={"expected_revision": 3, "operational_role_ids": [roles.json()[0]["id"]]},
    )
    assert audience.status_code == 200
    published = await auth_client.post(
        f"{version_url}/publish",
        headers=mutation_headers(csrf, key="recovered-publish"),
        json={"expected_revision": 4},
    )
    assert published.status_code == 200


@pytest.mark.parametrize(
    ("case", "status", "code"),
    [
        ("stale", 409, "REVISION_CONFLICT"),
        ("bound", 409, "MENU_DEPENDENCY_EXISTS"),
        ("published", 409, "TRAINING_VERSION_IMMUTABLE"),
        ("archived", 409, "TRAINING_VERSION_IMMUTABLE"),
        ("menu_draft", 409, "MENU_DEPENDENCY_INVALID"),
        ("menu_archived", 409, "MENU_DEPENDENCY_INVALID"),
        ("foreign_menu", 404, "RESOURCE_NOT_FOUND"),
        ("other_location_menu", 404, "RESOURCE_NOT_FOUND"),
        ("missing_menu", 404, "RESOURCE_NOT_FOUND"),
        ("foreign_version", 404, "RESOURCE_NOT_FOUND"),
        ("csrf", 403, "CSRF_INVALID"),
        ("mfa", 403, "MFA_REQUIRED"),
        ("admin", 404, "RESOURCE_NOT_FOUND"),
    ],
)
async def test_dependency_recovery_guards_are_atomic(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    case: str,
    status: int,
    code: str,
) -> None:
    org_id, loc_id, actor_id, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org_id}/locations/{loc_id}/training-versions"
    response = await auth_client.post(
        base, headers=mutation_headers(csrf, key="guard-draft"), json={"base_version_id": None}
    )
    assert response.status_code == 201
    version_id = UUID(response.json()["id"])
    version = await db_session.get_one(TrainingVersion, version_id)
    if case in {"published", "archived"}:
        version.status = case
        version.published_by_user_id = actor_id
        version.published_at = FIXED_NOW
        version.archived_at = FIXED_NOW if case == "archived" else None
    menu_org_id, menu_loc_id = org_id, loc_id
    if case in {"foreign_menu", "other_location_menu"}:
        org = (
            make_organization()
            if case == "foreign_menu"
            else await db_session.get_one(Organization, org_id)
        )
        location = make_location(org)
        db_session.add_all([org, location])
        await db_session.flush()
        menu_org_id, menu_loc_id = org.id, location.id
    menu = make_menu(menu_org_id, menu_loc_id)
    db_session.add(menu)
    await db_session.flush()
    menu_version = make_menu_version(
        menu,
        actor_id,
        status=case.removeprefix("menu_")
        if case in {"menu_draft", "menu_archived"}
        else "published",
    )
    if menu_version.status != "draft":
        menu_version.published_by_user_id = actor_id
        menu_version.published_at = FIXED_NOW
        menu_version.archived_at = FIXED_NOW if menu_version.status == "archived" else None
    db_session.add(menu_version)
    await db_session.flush()
    if case == "bound":
        db_session.add(
            TrainingVersionMenuDependency(
                training_version_id=version_id, menu_version_id=menu_version.id
            )
        )
    if case == "mfa":
        login = await db_session.scalar(select(Session).where(Session.user_id == actor_id))
        assert login is not None
        login.mfa_verified_at = None
    if case == "admin":
        access = await db_session.scalar(select(AdminAccess).where(AdminAccess.user_id == actor_id))
        assert access is not None
        access.status = "revoked"
        access.revoked_at = FIXED_NOW
    target_version_id = version_id
    if case == "foreign_version":
        foreign_org = make_organization()
        foreign_location = make_location(foreign_org)
        db_session.add_all([foreign_org, foreign_location])
        await db_session.flush()
        foreign_training = make_training(foreign_org.id, foreign_location.id)
        db_session.add(foreign_training)
        await db_session.flush()
        foreign_version = make_training_version(foreign_training, actor_id)
        db_session.add(foreign_version)
        target_version_id = foreign_version.id
    await db_session.commit()
    result = await auth_client.put(
        f"{base}/{target_version_id}/menu-dependency",
        headers=mutation_headers("invalid" if case == "csrf" else csrf),
        json={
            "expected_revision": 1 if case == "stale" else 0,
            "menu_version_id": str(uuid4() if case == "missing_menu" else menu_version.id),
        },
    )
    assert result.status_code == status
    assert result.json()["code"] == code
    db_session.expire_all()
    assert (await db_session.get_one(TrainingVersion, version_id)).revision == 0
    assert await db_session.scalar(
        select(func.count()).select_from(TrainingVersionMenuDependency)
    ) == (1 if case == "bound" else 0)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_menu_dependency_bound")
        )
        == 0
    )


async def test_concurrent_recovery_has_one_winner(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    org_id, loc_id, actor_id, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org_id}/locations/{loc_id}/training-versions"
    draft = await auth_client.post(
        base, headers=mutation_headers(csrf, key="race-draft"), json={"base_version_id": None}
    )
    assert draft.status_code == 201
    menu = make_menu(org_id, loc_id)
    db_session.add(menu)
    await db_session.flush()
    menu_version = make_menu_version(
        menu, actor_id, status="published", published_by_user_id=actor_id, published_at=FIXED_NOW
    )
    db_session.add(menu_version)
    await db_session.commit()

    async def bind() -> int:
        response = await auth_client.put(
            f"{base}/{draft.json()['id']}/menu-dependency",
            headers=mutation_headers(csrf),
            json={"expected_revision": 0, "menu_version_id": str(menu_version.id)},
        )
        return response.status_code

    assert sorted(await asyncio.gather(bind(), bind())) == [200, 409]
    assert (
        await db_session.scalar(select(func.count()).select_from(TrainingVersionMenuDependency))
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_menu_dependency_bound")
        )
        == 1
    )
