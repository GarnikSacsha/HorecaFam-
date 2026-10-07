from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Cookies
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AcademyArticle,
    Asset,
    EmployeeProfile,
    Organization,
    OrganizationMembership,
    Session,
)
from tests.api.test_employee_menu_api import attach_employee
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.factories.identity import make_location, make_organization, make_role
from tests.integration.test_training_assets import FakePrivateStorage


async def test_academy_publication_scope_revision_and_optional_reading(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    org, loc, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org}/locations/{loc}/academy"
    payload = {
        "slug": "welcome",
        "title_uk": "Перші секунди",
        "summary_uk": "Початок розмови",
        "body_uk": "Привітайте гостя та запропонуйте допомогу.",
        "category": "service",
        "all_positions": True,
        "operational_role_ids": [],
        "status": "draft",
        "position": 0,
    }
    created = await auth_client.post(
        base, headers=mutation_headers(csrf, key="article"), json=payload
    )
    assert created.status_code == 201
    article = created.json()
    replay = await auth_client.post(
        base, headers=mutation_headers(csrf, key="article"), json=payload
    )
    assert replay.status_code == 201 and replay.json()["id"] == article["id"]
    assert (
        await auth_client.patch(
            base + f"/{article['id']}", json={**payload, "expected_revision": 0}
        )
    ).status_code == 403
    published = await auth_client.patch(
        base + f"/{article['id']}",
        headers=mutation_headers(csrf),
        json={**payload, "status": "published", "expected_revision": 0},
    )
    assert published.status_code == 200
    assert (
        await auth_client.patch(
            base + f"/{article['id']}",
            headers=mutation_headers(csrf),
            json={**payload, "expected_revision": 0},
        )
    ).status_code == 409
    hidden = await auth_client.post(
        base, headers=mutation_headers(csrf, key="draft"), json={**payload, "slug": "draft"}
    )
    assert hidden.status_code == 201
    foreign = await auth_client.get(base.replace(str(loc), str(uuid4())))
    assert foreign.status_code == 404
    await attach_employee(auth_client, db_session, organization_id=org, location_id=loc)
    before = (await auth_client.get("/api/v1/me/training")).json()
    listing = await auth_client.get("/api/v1/me/academy")
    assert listing.status_code == 200
    assert [item["slug"] for item in listing.json()["items"]] == ["welcome"]
    assert (await auth_client.get("/api/v1/me/academy/welcome")).json()["body_uk"] == payload[
        "body_uk"
    ]
    assert (await auth_client.get("/api/v1/me/academy/draft")).status_code == 404
    assert (await auth_client.get(base)).status_code == 403
    assert (await auth_client.get("/api/v1/me/training")).json() == before
    auth_client.cookies.clear()
    assert (await auth_client.get("/api/v1/me/academy")).status_code == 401


async def test_catalog_preserves_edits_and_enforces_current_position_and_location(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    org, loc, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    organization = await db_session.get_one(Organization, org)
    roles = [
        make_role(organization, code=code) for code in ("catalog-waiter", "runner", "bartender")
    ]
    elsewhere = make_location(organization, name="Elsewhere")
    foreign_org = make_organization(name="Foreign")
    foreign_role = make_role(foreign_org, code="foreign")
    db_session.add_all([*roles, elsewhere, foreign_org, foreign_role])
    await db_session.commit()
    base = f"/api/v1/organizations/{org}/locations/{loc}/academy"
    seed = dict(
        zip(
            ("waiter_role_id", "runner_role_id", "bartender_role_id"),
            map(lambda role: str(role.id), roles),
            strict=True,
        )
    )
    denied = await auth_client.post(
        base + "/seed",
        headers=mutation_headers(csrf),
        json={**seed, "runner_role_id": str(foreign_role.id)},
    )
    assert denied.status_code == 404
    assert list(await db_session.scalars(select(AcademyArticle.id))) == []
    created = await auth_client.post(base + "/seed", headers=mutation_headers(csrf), json=seed)
    assert created.status_code == 200 and created.json()["created_count"] == 13
    articles = (await auth_client.get(base)).json()["items"]
    assert len(articles) == 13 and all(article["status"] == "draft" for article in articles)
    assert sum(article["all_positions"] for article in articles) == 4
    for article in articles:
        payload = {
            key: value
            for key, value in article.items()
            if key not in {"id", "revision", "created_at", "updated_at"}
        }
        updated = await auth_client.patch(
            base + f"/{article['id']}",
            headers=mutation_headers(csrf),
            json={
                **payload,
                "expected_revision": 0,
                "status": "published",
                "summary_uk": "Відредаговано людиною",
            },
        )
        assert updated.status_code == 200
    repeated = await auth_client.post(base + "/seed", headers=mutation_headers(csrf), json=seed)
    assert repeated.json()["created_count"] == 0
    assert all(
        article["summary_uk"] == "Відредаговано людиною"
        for article in (await auth_client.get(base)).json()["items"]
    )
    admin_cookies = Cookies(auth_client.cookies)
    employee_user = await attach_employee(
        auth_client, db_session, organization_id=org, location_id=loc
    )
    profile = await db_session.scalar(
        select(EmployeeProfile)
        .join(OrganizationMembership, OrganizationMembership.id == EmployeeProfile.membership_id)
        .where(OrganizationMembership.user_id == employee_user)
    )
    assert profile is not None
    assert len((await auth_client.get("/api/v1/me/academy")).json()["items"]) == 4
    assert (await auth_client.get("/api/v1/me/academy/bar-station")).status_code == 404
    for role, slug in zip(roles, ("large-table", "runner-table-check", "bar-station"), strict=True):
        profile.operational_role_id = role.id
        await db_session.commit()
        visible = (await auth_client.get("/api/v1/me/academy?limit=3")).json()
        assert len(visible["items"]) == 3 and visible["next_offset"] == 3
        assert (
            len((await auth_client.get("/api/v1/me/academy?offset=3&limit=50")).json()["items"])
            == 4
        )
        assert (await auth_client.get(f"/api/v1/me/academy/{slug}")).status_code == 200
    assert (await auth_client.get("/api/v1/me/academy/runner-table-check")).status_code == 404
    profile.location_id = elsewhere.id
    await db_session.commit()
    assert (await auth_client.get("/api/v1/me/academy")).json()["items"] == []
    assert (await auth_client.get("/api/v1/me/academy/bar-station")).status_code == 404
    # Відкликання публікації діє і для вже відомої адреси.
    auth_client.cookies = admin_cookies
    target = articles[0]
    payload = {
        key: value
        for key, value in target.items()
        if key not in {"id", "revision", "created_at", "updated_at"}
    }
    result = await auth_client.patch(
        base + f"/{target['id']}",
        headers=mutation_headers(csrf),
        json={**payload, "expected_revision": 1},
    )
    assert result.status_code == 200
    await attach_employee(auth_client, db_session, organization_id=org, location_id=loc)
    assert (await auth_client.get(f"/api/v1/me/academy/{target['slug']}")).status_code == 404


async def test_cover_is_scoped_ready_protected_and_cannot_be_archived_while_linked(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    org, loc, admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    storage = FakePrivateStorage()
    auth_app.state.private_storage = storage
    asset = Asset(
        organization_id=org,
        location_id=loc,
        status="ready",
        object_key="private/academy/cover",
        original_filename="cover.webp",
        mime_type="image/webp",
        size_bytes=100,
        sha256="a" * 64,
        created_by_user_id=admin,
        upload_expires_at=FIXED_NOW + timedelta(minutes=15),
        ready_at=FIXED_NOW,
    )
    db_session.add(asset)
    await db_session.commit()
    base = f"/api/v1/organizations/{org}/locations/{loc}/academy"
    payload = {
        "slug": "cover",
        "title_uk": "Обкладинка",
        "summary_uk": "Опис",
        "body_uk": "Текст",
        "category": "service",
        "all_positions": True,
        "cover_asset_id": str(asset.id),
        "status": "published",
    }
    invalid = await auth_client.post(
        base,
        headers=mutation_headers(csrf, key="missing-cover"),
        json={**payload, "cover_asset_id": str(uuid4())},
    )
    assert invalid.status_code == 404
    response = await auth_client.post(
        base, headers=mutation_headers(csrf, key="cover"), json=payload
    )
    assert response.status_code == 201
    asset_url = f"/api/v1/organizations/{org}/locations/{loc}/assets/{asset.id}"
    assert (await auth_client.delete(asset_url, headers=mutation_headers(csrf))).status_code == 409
    await attach_employee(auth_client, db_session, organization_id=org, location_id=loc)
    assert "private/academy" not in (await auth_client.get("/api/v1/me/academy/cover")).text
    access = await auth_client.get("/api/v1/me/academy/cover/cover")
    assert access.status_code == 200 and access.json()["expires_in"] == 300
    assert storage.accessed_keys == [asset.object_key]
    article = await db_session.scalar(select(AcademyArticle).where(AcademyArticle.slug == "cover"))
    assert article is not None
    article.status = "draft"
    await db_session.commit()
    assert (await auth_client.get("/api/v1/me/academy/cover/cover")).status_code == 404
    assert storage.accessed_keys == [asset.object_key]


async def test_academy_requires_mfa_and_valid_audience(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    org, loc, admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org}/locations/{loc}/academy"
    payload = {
        "slug": "test",
        "title_uk": "Тест",
        "summary_uk": "Опис",
        "body_uk": "Текст",
        "category": "service",
    }
    for audience in ({}, {"all_positions": True, "operational_role_ids": [str(uuid4())]}):
        assert (
            await auth_client.post(
                base, headers=mutation_headers(csrf, key=str(uuid4())), json={**payload, **audience}
            )
        ).status_code == 422
    assert (
        await auth_client.post(
            base,
            headers=mutation_headers(csrf, key="foreign-role"),
            json={**payload, "operational_role_ids": [str(uuid4())]},
        )
    ).status_code == 404
    record = await db_session.scalar(select(Session).where(Session.user_id == admin))
    assert record is not None
    record.mfa_verified_at = None
    await db_session.commit()
    assert (await auth_client.get(base)).status_code == 403
    assert (
        await auth_client.post(
            base, headers=mutation_headers(csrf, key="mfa"), json={**payload, "all_positions": True}
        )
    ).status_code == 403


@pytest.mark.parametrize("membership_status", ["pending", "disabled"])
async def test_inactive_employee_cannot_read_academy(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession, membership_status: str
) -> None:
    org, loc, _admin, _csrf = await arrange_admin(auth_client, auth_app, db_session)
    await attach_employee(
        auth_client, db_session, organization_id=org, location_id=loc, status=membership_status
    )
    assert (await auth_client.get("/api/v1/me/academy")).status_code == 403
