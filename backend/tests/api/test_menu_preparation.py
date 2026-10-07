from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.test_employee_menu_api import attach_employee
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_menu_publication_api import arrange_ready_draft


async def test_preparation_details_survive_publication_copy_and_partial_edit(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    org, loc, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    draft = await arrange_ready_draft(
        auth_client, organization_id=org, location_id=loc, csrf=csrf, key_prefix="bar"
    )
    versions = f"/api/v1/organizations/{org}/locations/{loc}/menu-versions"
    base = f"{versions}/{draft['id']}"
    item = (await auth_client.get(base + "/items")).json()["items"][0]
    preparation = {
        "volume_ml": 250,
        "technique_uk": "Build",
        "glassware_uk": "Склянка",
        "garnish_uk": "За карткою",
        "serving_standard_uk": "За затвердженою карткою",
        "preparation_seconds": 90,
    }
    response = await auth_client.patch(
        base + f"/items/{item['item_id']}",
        headers=mutation_headers(csrf),
        json={"expected_revision": draft["revision"], "preparation": preparation},
    )
    assert response.status_code == 200
    assert response.json()["item"]["preparation"] == preparation
    invalid = await auth_client.patch(
        base + f"/items/{item['item_id']}",
        headers=mutation_headers(csrf),
        json={"expected_revision": response.json()["revision"], "preparation": {"volume_ml": -1}},
    )
    assert invalid.status_code == 422
    published = await auth_client.post(
        base + "/publish",
        headers=mutation_headers(csrf, key="bar-publish"),
        json={"expected_revision": response.json()["revision"]},
    )
    assert published.status_code == 200
    copied = await auth_client.post(
        versions,
        headers=mutation_headers(csrf, key="bar-copy"),
        json={"copy_from_version_id": draft["id"]},
    )
    assert copied.status_code == 201
    base = f"{versions}/{copied.json()['id']}"
    copied_item = (await auth_client.get(base + f"/items/{item['item_id']}")).json()
    assert copied_item["preparation"] == preparation
    assert copied_item["delta_kind"] == "unchanged"
    changed = await auth_client.patch(
        base + f"/items/{item['item_id']}",
        headers=mutation_headers(csrf),
        json={"expected_revision": copied.json()["revision"], "price_minor": 15000},
    )
    assert changed.status_code == 200
    assert changed.json()["item"]["preparation"] == preparation
    cleared = await auth_client.patch(
        base + f"/items/{item['item_id']}",
        headers=mutation_headers(csrf),
        json={"expected_revision": changed.json()["revision"], "preparation": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["item"]["preparation"] is None
    assert "preparation" in cleared.json()["item"]["changed_field_codes"]
    assert cleared.json()["item"]["training_impact"] == "review"
    history = (await auth_client.get(f"/api/v1/organizations/{org}/menu-change-history")).json()
    assert history["items"][0]["old_values"]["preparation"] == preparation
    assert history["items"][0]["new_values"]["preparation"] is None
    await attach_employee(auth_client, db_session, organization_id=org, location_id=loc)
    visible = await auth_client.get(f"/api/v1/me/menu/items/{item['item_id']}")
    assert visible.status_code == 200
    assert visible.json()["preparation"] == preparation
