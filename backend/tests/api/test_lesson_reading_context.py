from uuid import UUID

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItemVersion, MenuItemVersionTranslation
from tests.api.test_employee_menu_api import attach_employee
from tests.api.test_employee_training_api import attach_training_assignment, first_lesson_id
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu


async def test_lesson_returns_its_module_and_bound_menu_card(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    org, location, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    await publish_menu(
        auth_client,
        organization_id=org,
        location_id=location,
        csrf=csrf,
        key_prefix="reader-menu",
    )
    draft = await arrange_ready_training(
        auth_client,
        organization_id=org,
        location_id=location,
        csrf=csrf,
        key_prefix="reader-training",
    )
    item = (await db_session.scalars(select(MenuItemVersion))).first()
    assert item is not None
    translation = await db_session.scalar(
        select(MenuItemVersionTranslation).where(
            MenuItemVersionTranslation.menu_item_version_id == item.id,
            MenuItemVersionTranslation.locale == "uk",
        )
    )
    assert translation is not None
    expected_name = translation.name
    expected_price = item.price_minor
    lesson_id = first_lesson_id(draft)
    base = f"/api/v1/organizations/{org}/locations/{location}/training-versions/{draft['id']}"
    block = await auth_client.post(
        f"{base}/lessons/{lesson_id}/content-blocks",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": draft["revision"],
            "type": "menu_item_card",
            "payload": {"menu_item_id": str(item.menu_item_id)},
        },
    )
    assert block.status_code == 200
    published = await auth_client.post(
        f"{base}/publish",
        headers=mutation_headers(csrf, key="reader-publish"),
        json={"expected_revision": block.json()["revision"]},
    )
    assert published.status_code == 200
    menus = f"/api/v1/organizations/{org}/locations/{location}/menu-versions"
    replacement = await auth_client.post(
        menus,
        headers=mutation_headers(csrf, key="reader-next-menu"),
        json={"copy_from_version_id": None},
    )
    assert replacement.status_code == 201
    next_menu = replacement.json()["id"]
    edited = await auth_client.patch(
        f"{menus}/{next_menu}/items/{item.menu_item_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "price_minor": 99999},
    )
    assert edited.status_code == 200
    next_published = await auth_client.post(
        f"{menus}/{next_menu}/publish",
        headers=mutation_headers(csrf, key="reader-next-menu-publish"),
        json={"expected_revision": edited.json()["revision"]},
    )
    assert next_published.status_code == 200
    user = await attach_employee(auth_client, db_session, organization_id=org, location_id=location)
    await attach_training_assignment(db_session, user_id=user, version_id=UUID(str(draft["id"])))
    home = (await auth_client.get("/api/v1/me/training")).json()
    response = await auth_client.get(f"/api/v1/me/training/lessons/{lesson_id}?locale=en")
    assert response.status_code == 200
    detail = response.json()
    assert detail.get("module_id") == home["modules"][0]["id"]
    card = detail["content_blocks"][1].get("menu_item")
    assert card is not None
    assert card["item_id"] == str(item.menu_item_id)
    assert card["name"] == expected_name
    assert card["price_minor"] == expected_price
    assert card["category_name"]
    assert card["section_name"]
    assert card["translation_fallback"] is True
    assert detail["content_blocks"][0].get("menu_item") is None
    assert detail["completed"] is False
    assert "source_reference" not in response.text
    assert "menu_item_version_id" not in response.text
