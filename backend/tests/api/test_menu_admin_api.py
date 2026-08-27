from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuVersion, Session
from app.security.tokens import hash_secret
from tests.factories.auth import make_admin_access
from tests.factories.identity import make_location, make_organization, make_user

FIXED_NOW = datetime(2030, 8, 27, 13, 0, tzinfo=UTC)


async def arrange_admin(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    *,
    mfa_verified: bool = True,
) -> tuple[UUID, UUID, UUID, str]:
    app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    location = make_location(organization)
    admin = make_user(email_normalized=f"menu-admin-{uuid4()}@example.com")
    db.add_all([organization, location, admin])
    await db.flush()
    db.add(
        make_admin_access(
            admin,
            scope="organization_admin",
            organization=organization,
        )
    )
    raw_session = f"menu-session-{uuid4()}"
    csrf_token = f"menu-csrf-{uuid4()}"
    db.add(
        Session(
            user_id=admin.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(csrf_token),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
            mfa_verified_at=FIXED_NOW if mfa_verified else None,
        )
    )
    await db.commit()
    client.cookies.set("horeca_session", raw_session, path="/api/v1")
    return organization.id, location.id, admin.id, csrf_token


def mutation_headers(csrf_token: str, *, key: str | None = None) -> dict[str, str]:
    headers = {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf_token,
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


async def test_admin_menu_api_supports_draft_hierarchy_and_item_workflow(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    versions_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions"
    create = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="create-draft"),
        json={"copy_from_version_id": None},
    )
    replay = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="create-draft"),
        json={"copy_from_version_id": None},
    )

    assert create.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == create.json()["id"]
    version_id = UUID(create.json()["id"])
    assert create.json()["status"] == "draft"
    assert create.json()["sections"] == []

    section_response = await auth_client.post(
        f"{versions_url}/{version_id}/sections",
        headers=mutation_headers(csrf),
        json={
            "name_uk": "Основне",
            "stable_code": "main",
            "position": 0,
            "expected_revision": 0,
        },
    )
    assert section_response.status_code == 200
    section_id = UUID(section_response.json()["section"]["id"])
    assert section_response.json()["revision"] == 1

    category_response = await auth_client.post(
        f"{versions_url}/{version_id}/categories",
        headers=mutation_headers(csrf),
        json={
            "section_id": str(section_id),
            "name_uk": "Супи",
            "stable_code": "soups",
            "position": 0,
            "expected_revision": 1,
        },
    )
    assert category_response.status_code == 200
    category_id = UUID(category_response.json()["category"]["id"])

    item_response = await auth_client.post(
        f"{versions_url}/{version_id}/items",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 2,
            "category_id": str(category_id),
            "stable_code": "borshch",
            "name_uk": "Борщ",
            "description_uk": None,
            "price_minor": 32500,
            "currency": "UAH",
            "availability": "available",
            "position": 0,
            "component_data_status": "unknown",
            "components": [],
            "allergen_data_status": "confirmed_none",
            "allergen_codes": [],
            "source_kind": "manual",
            "source_reference": None,
            "source_item_key": None,
        },
    )
    assert item_response.status_code == 200
    item_id = UUID(item_response.json()["item"]["item_id"])
    assert item_response.json()["item"]["delta_kind"] == "added"

    patch = await auth_client.patch(
        f"{versions_url}/{version_id}/items/{item_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 3, "price_minor": 35000},
    )
    assert patch.status_code == 200
    assert patch.json()["revision"] == 4

    detail = await auth_client.get(f"{versions_url}/{version_id}")
    listing = await auth_client.get(f"{versions_url}/{version_id}/items")
    item_detail = await auth_client.get(f"{versions_url}/{version_id}/items/{item_id}")
    navigation = await auth_client.get(versions_url)

    assert detail.status_code == listing.status_code == item_detail.status_code == 200
    assert detail.json()["item_count"] == 1
    assert listing.json()["revision"] == 4
    assert listing.json()["items"][0]["price_minor"] == 35000
    assert navigation.json()["draft"]["id"] == str(version_id)


async def test_admin_menu_mutations_require_csrf_mfa_and_same_tenant(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions"
    no_mfa = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="no-mfa"),
        json={"copy_from_version_id": None},
    )
    assert no_mfa.status_code == 403
    assert no_mfa.json()["code"] == "MFA_REQUIRED"

    auth_client.cookies.clear()
    organization_id, location_id, _admin_id, _csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    missing_csrf = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions",
        headers={"Origin": "https://frontend.test", "Idempotency-Key": "missing-csrf"},
        json={"copy_from_version_id": None},
    )
    foreign = await auth_client.get(
        f"/api/v1/organizations/{uuid4()}/locations/{location_id}/menu-versions"
    )

    assert missing_csrf.status_code == 403
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "RESOURCE_NOT_FOUND"
    assert await db_session.scalar(select(func.count()).select_from(MenuVersion)) == 0


async def test_admin_menu_openapi_is_exact_and_excludes_internal_fields(
    auth_client: AsyncClient,
) -> None:
    document = (await auth_client.get("/openapi.json")).json()
    paths = document["paths"]
    prefix = "/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions"

    assert set(paths[prefix]) == {"get", "post"}
    assert set(paths[f"{prefix}/{{version_id}}/sections"]) == {"post"}
    assert set(paths[f"{prefix}/{{version_id}}/sections/{{section_id}}"]) == {
        "patch",
        "delete",
    }
    assert set(paths[f"{prefix}/{{version_id}}/items"]) == {"get", "post"}
    serialized = str(document["components"]["schemas"])
    assert "verified_by_user_id" not in serialized
    assert "source_checksum" not in serialized
