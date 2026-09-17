from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItemVersion, User
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_menu_publication_api import arrange_ready_draft


async def test_menu_history_records_business_changes_and_skips_noops(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="history",
    )
    item = await db_session.scalar(
        select(MenuItemVersion).where(MenuItemVersion.menu_version_id == UUID(str(draft["id"])))
    )
    assert item is not None
    old_price = item.price_minor
    admin = await db_session.get(User, admin_id)
    assert admin is not None
    email = admin.email_normalized
    url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}"
        f"/menu-versions/{draft['id']}/items/{item.menu_item_id}"
    )
    history_url = f"/api/v1/organizations/{organization_id}/menu-change-history"
    first = await auth_client.patch(
        url,
        headers=mutation_headers(csrf),
        json={
            "expected_revision": draft["revision"],
            "price_minor": 45600,
        },
    )
    assert first.status_code == 200
    response = await auth_client.get(history_url)
    assert response.status_code == 200
    event = response.json()["items"][0]
    assert event["actor_email"] == email
    assert event["old_values"]["price_minor"] == old_price
    assert event["new_values"]["price_minor"] == 45600
    assert event["action"] == "updated"
    assert "source_reference" not in event["new_values"]
    count = len(response.json()["items"])
    no_op = await auth_client.patch(
        url,
        headers=mutation_headers(csrf),
        json={
            "expected_revision": first.json()["revision"],
            "price_minor": 45600,
        },
    )
    assert no_op.status_code == 200
    stale = await auth_client.patch(
        url,
        headers=mutation_headers(csrf),
        json={
            "expected_revision": draft["revision"],
            "price_minor": 99900,
        },
    )
    assert stale.status_code == 409
    assert len((await auth_client.get(history_url)).json()["items"]) == count
    removed = await auth_client.delete(
        url,
        headers=mutation_headers(csrf),
        params={"expected_revision": no_op.json()["revision"]},
    )
    assert removed.status_code == 200
    page = (await auth_client.get(history_url, params={"limit": 1})).json()
    assert page["items"][0]["action"] == "removed"
    assert page["items"][0]["old_values"]["price_minor"] == 45600
    assert page["items"][0]["new_values"] is None
    assert page["next_cursor"]
    next_page = (
        await auth_client.get(
            history_url,
            params={
                "limit": 1,
                "cursor": page["next_cursor"],
            },
        )
    ).json()
    assert next_page["items"][0]["id"] != page["items"][0]["id"]
    assert (await auth_client.get(history_url, params={"cursor": "invalid"})).status_code == 422
    assert (
        await auth_client.get(f"/api/v1/organizations/{uuid4()}/menu-change-history")
    ).status_code in (403, 404)


async def test_menu_history_requires_admin_mfa(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, _, _, _ = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )
    response = await auth_client.get(f"/api/v1/organizations/{organization_id}/menu-change-history")
    assert response.status_code == 403


async def test_menu_history_keeps_composition_and_author_snapshot(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="composition-history",
    )
    item = await db_session.scalar(
        select(MenuItemVersion).where(MenuItemVersion.menu_version_id == UUID(str(draft["id"])))
    )
    assert item is not None
    admin = await db_session.get(User, admin_id)
    assert admin is not None
    email = admin.email_normalized
    url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}"
        f"/menu-versions/{draft['id']}/items"
    )
    created = await auth_client.post(
        url,
        headers=mutation_headers(csrf),
        json={
            "expected_revision": draft["revision"],
            "category_id": str(item.menu_version_category_id),
            "name_uk": "Тестова кава",
            "price_minor": 10000,
            "position": 1,
            "component_data_status": "confirmed_present",
            "components": [{"name_uk": "Вівсяне молоко", "optional": False, "position": 0}],
            "allergen_data_status": "unknown",
            "allergen_codes": [],
        },
    )
    assert created.status_code == 200
    admin.email_normalized = "changed-author@example.com"
    await db_session.commit()
    response = await auth_client.get(f"/api/v1/organizations/{organization_id}/menu-change-history")
    assert response.status_code == 200
    event = response.json()["items"][0]
    assert event["action"] == "created"
    assert event["actor_email"] == email
    assert event["old_values"] is None
    assert event["new_values"]["components"] == [{"name": "Вівсяне молоко", "optional": False}]
