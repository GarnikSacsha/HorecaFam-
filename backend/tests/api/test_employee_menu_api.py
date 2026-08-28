from copy import deepcopy
from datetime import timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployeeProfile, Organization, Session
from app.security.tokens import hash_secret
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.api.test_menu_import_api import import_payload
from tests.api.test_menu_publication_api import arrange_ready_draft
from tests.factories.identity import make_membership, make_role, make_user


async def attach_employee(
    client: AsyncClient,
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    status: str = "active",
    preferred_locale: str = "uk",
) -> UUID:
    organization = await db.get_one(Organization, organization_id)
    role = make_role(organization, code=f"role-{uuid4()}")
    user = make_user(
        email_normalized=f"menu-employee-{uuid4()}@example.com",
        preferred_locale=preferred_locale,
    )
    membership = make_membership(
        organization,
        user,
        status=status,
        activated_at=FIXED_NOW if status == "active" else None,
        disabled_at=FIXED_NOW if status == "disabled" else None,
    )
    db.add_all([role, user, membership])
    await db.flush()
    db.add(
        EmployeeProfile(
            membership_id=membership.id,
            organization_id=organization_id,
            first_name="Марія",
            last_name="Тестова",
            operational_role_id=role.id,
            location_id=location_id,
        )
    )
    raw_session = f"employee-menu-session-{uuid4()}"
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(f"employee-menu-csrf-{uuid4()}"),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
        )
    )
    await db.commit()
    client.cookies.clear()
    client.cookies.set("horeca_session", raw_session, path="/api/v1")
    return user.id


async def test_employee_reads_only_current_published_location_menu_with_locale_fallback(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    first_draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="employee-current",
    )
    versions_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions"
    version_id = UUID(str(first_draft["id"]))
    published = await auth_client.post(
        f"{versions_url}/{version_id}/publish",
        headers=mutation_headers(csrf, key="employee-current-publish"),
        json={"expected_revision": first_draft["revision"]},
    )
    assert published.status_code == 200

    # A later Draft is intentionally different and must remain Employee-invisible.
    second_draft = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="employee-hidden-draft"),
        json={"copy_from_version_id": None},
    )
    second_id = UUID(second_draft.json()["id"])
    draft_items = await auth_client.get(f"{versions_url}/{second_id}/items")
    item_id = UUID(draft_items.json()["items"][0]["item_id"])
    changed = await auth_client.patch(
        f"{versions_url}/{second_id}/items/{item_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 0, "price_minor": 99999},
    )
    assert changed.status_code == 200

    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        preferred_locale="en",
    )
    listing = await auth_client.get("/api/v1/me/menu", params={"q": "бор"})
    filtered = await auth_client.get(
        "/api/v1/me/menu",
        params={"category_id": listing.json()["menu"]["sections"][0]["categories"][0]["id"]},
    )
    detail = await auth_client.get(f"/api/v1/me/menu/items/{item_id}")
    missing = await auth_client.get(f"/api/v1/me/menu/items/{uuid4()}")

    assert listing.status_code == filtered.status_code == detail.status_code == 200
    assert listing.json()["menu"]["menu_version_id"] == str(version_id)
    assert listing.json()["items"][0]["price_minor"] == 32500
    assert listing.json()["items"][0]["content_locale"] == "uk"
    assert listing.json()["items"][0]["translation_fallback"] is True
    assert filtered.json()["items"][0]["item_id"] == str(item_id)
    assert detail.json()["description"] == "Опис"
    assert detail.json()["components"] == []
    assert detail.json()["allergens"] == []
    assert missing.status_code == 404
    for forbidden in (
        "source_payload",
        "source_checksum",
        "source_reference",
        "source_item_key",
        "verified_by_user_id",
        "review_revision",
    ):
        assert forbidden not in listing.text
        assert forbidden not in detail.text


async def test_employee_menu_empty_state_and_active_profile_boundary(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, _csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    empty = await auth_client.get("/api/v1/me/menu")
    assert empty.status_code == 200
    assert empty.json() == {"menu": None, "items": [], "next_cursor": None}

    auth_client.cookies.clear()
    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        status="disabled",
    )
    denied = await auth_client.get("/api/v1/me/menu")
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"


async def test_employee_menu_component_search_and_cursor_pagination_are_stable(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    payload = deepcopy(import_payload())
    sections = cast(list[dict[str, Any]], payload["sections"])
    items = cast(list[dict[str, Any]], sections[0]["categories"][0]["items"])
    items[0]["component_data_status"] = "confirmed_present"
    items[0]["components"] = [
        {
            "stable_code": "beetroot",
            "name_uk": "Буряк",
            "optional": False,
            "position": 0,
        }
    ]
    for position, (stable_code, name_uk) in enumerate(
        (("varenyky", "Вареники"), ("uzvar", "Узвар")),
        start=1,
    ):
        item = deepcopy(items[0])
        item.update(
            {
                "source_key": f"item-{stable_code}",
                "stable_code": stable_code,
                "name_uk": name_uk,
                "position": position,
                "component_data_status": "confirmed_none",
                "components": [],
            }
        )
        items.append(item)

    imports_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    preview = await auth_client.post(
        imports_url,
        headers=mutation_headers(csrf, key="employee-pagination-preview"),
        json=payload,
    )
    assert preview.status_code == 201
    confirm = await auth_client.post(
        f"{imports_url}/{preview.json()['id']}/confirm",
        headers=mutation_headers(csrf, key="employee-pagination-confirm"),
        json={"expected_revision": 0, "acknowledge_warnings": False},
    )
    assert confirm.status_code == 200
    draft = confirm.json()["draft"]
    publish = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions/"
        f"{draft['id']}/publish",
        headers=mutation_headers(csrf, key="employee-pagination-publish"),
        json={"expected_revision": draft["revision"]},
    )
    assert publish.status_code == 200

    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    component_match = await auth_client.get("/api/v1/me/menu", params={"q": "буряк"})
    first_page = await auth_client.get("/api/v1/me/menu", params={"limit": 1})
    first_page_replay = await auth_client.get("/api/v1/me/menu", params={"limit": 1})
    second_page = await auth_client.get(
        "/api/v1/me/menu",
        params={"limit": 1, "cursor": first_page.json()["next_cursor"]},
    )
    invalid_cursor = await auth_client.get(
        "/api/v1/me/menu", params={"cursor": "not-a-valid-cursor"}
    )

    assert component_match.status_code == 200
    assert [item["name"] for item in component_match.json()["items"]] == ["Борщ"]
    assert first_page.status_code == first_page_replay.status_code == second_page.status_code == 200
    assert first_page.json()["next_cursor"] == first_page_replay.json()["next_cursor"]
    assert first_page.json()["items"][0]["item_id"] != second_page.json()["items"][0]["item_id"]
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["code"] == "VALIDATION_ERROR"


async def test_employee_menu_openapi_has_no_tenant_selector_or_internal_provenance(
    auth_client: AsyncClient,
) -> None:
    document = (await auth_client.get("/openapi.json")).json()
    assert set(document["paths"]["/api/v1/me/menu"]) == {"get"}
    assert set(document["paths"]["/api/v1/me/menu/items/{item_id}"]) == {"get"}
    parameters = document["paths"]["/api/v1/me/menu"]["get"]["parameters"]
    assert {parameter["name"] for parameter in parameters} == {
        "q",
        "section_id",
        "category_id",
        "cursor",
        "limit",
    }
    serialized = str(document["components"]["schemas"])
    employee_schemas = {
        key: value
        for key, value in document["components"]["schemas"].items()
        if key.startswith("EmployeeMenu")
    }
    assert "source_reference" not in str(employee_schemas)
    assert "source_checksum" in serialized
