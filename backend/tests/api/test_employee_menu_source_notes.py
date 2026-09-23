from uuid import UUID

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItemVersion, MenuItemVersionTranslation
from tests.api.test_employee_menu_api import attach_employee
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_menu_publication_api import arrange_ready_draft
from tests.unit.test_menu_source_notes import REFERENCE


async def test_published_item_notes_preserve_unknown_facts(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="guest-note",
    )
    version_id = UUID(str(draft["id"]))
    item = (
        await db_session.scalars(
            select(MenuItemVersion).where(MenuItemVersion.menu_version_id == version_id)
        )
    ).one()
    translation = (
        await db_session.scalars(
            select(MenuItemVersionTranslation).where(
                MenuItemVersionTranslation.menu_item_version_id == item.id,
                MenuItemVersionTranslation.locale == "uk",
            )
        )
    ).one()
    item.source_reference = REFERENCE
    item.source_item_key = "dish-1854644"
    item.component_data_status = "unknown"
    item.allergen_data_status = "unknown"
    translation.name = 'Морозиво Maropu "Пломбір"'
    translation.description = "Ніжний вершковий пломбір із насиченим молочним смаком."
    item_id = item.menu_item_id
    await db_session.commit()
    response = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/publish",
        headers=mutation_headers(csrf, key="guest-note-publish"),
        json={"expected_revision": draft["revision"], "demo_with_unknown_facts": True},
    )
    assert response.status_code == 200
    await attach_employee(
        auth_client, db_session, organization_id=organization_id, location_id=location_id
    )
    response = await auth_client.get(f"/api/v1/me/menu/items/{item_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["source_note"]["allergen_labels"] == ["Молоко"]
    assert body["source_note"]["verification_status"] == "unverified"
    assert body["allergen_data_status"] == "unknown"
    assert body["allergens"] == body["components"] == []
    assert "source_reference" not in response.text
    assert "source_item_key" not in response.text
