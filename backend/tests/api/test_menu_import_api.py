from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import MenuImport, MenuVersion
from app.schemas.menu import MenuImportCreate
from app.services.menu_imports import _canonical_payload
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers


def import_payload(*, allergen_codes: list[str] | None = None) -> dict[str, object]:
    codes = allergen_codes or []
    return {
        "source_filename": "menu.json",
        "source_reference": "local-admin-upload",
        "sections": [
            {
                "source_key": "section-main",
                "stable_code": "main",
                "name_uk": "Основне",
                "position": 0,
                "categories": [
                    {
                        "source_key": "category-soups",
                        "stable_code": "soups",
                        "name_uk": "Супи",
                        "position": 0,
                        "items": [
                            {
                                "source_key": "item-borshch",
                                "stable_code": "borshch",
                                "name_uk": "Борщ",
                                "description_uk": "Опис",
                                "price_minor": 32500,
                                "currency": "UAH",
                                "availability": "available",
                                "position": 0,
                                "component_data_status": "confirmed_none",
                                "components": [],
                                "allergen_data_status": (
                                    "confirmed_present" if codes else "confirmed_none"
                                ),
                                "allergen_codes": codes,
                                "source_kind": "json_import",
                                "source_reference": "menu.json",
                                "source_item_key": "item-borshch",
                            }
                        ],
                    }
                ],
            }
        ],
    }


async def test_admin_json_import_preview_replay_and_confirm_create_only_draft(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    headers = mutation_headers(csrf, key="import-preview")
    created = await auth_client.post(url, headers=headers, json=import_payload())
    replay = await auth_client.post(url, headers=headers, json=import_payload())

    assert created.status_code == replay.status_code == 201
    assert created.json()["id"] == replay.json()["id"]
    assert created.json()["status"] == "ready_for_review"
    assert created.json()["item_count"] == 1
    assert len(created.json()["source_checksum"]) == 64
    assert "source_payload" not in created.json()

    import_id = UUID(created.json()["id"])
    detail = await auth_client.get(f"{url}/{import_id}")
    confirm = await auth_client.post(
        f"{url}/{import_id}/confirm",
        headers=mutation_headers(csrf, key="import-confirm"),
        json={"expected_revision": 0, "acknowledge_warnings": False},
    )
    confirm_replay = await auth_client.post(
        f"{url}/{import_id}/confirm",
        headers=mutation_headers(csrf, key="import-confirm"),
        json={"expected_revision": 0, "acknowledge_warnings": False},
    )

    assert detail.status_code == 200
    assert confirm.status_code == confirm_replay.status_code == 200
    assert confirm.json()["import"]["status"] == "confirmed"
    assert confirm.json()["draft"]["status"] == "draft"
    assert confirm.json()["draft"]["item_count"] == 1
    assert confirm_replay.json()["draft"]["id"] == confirm.json()["draft"]["id"]
    assert (
        await db_session.scalar(
            select(func.count()).select_from(MenuVersion).where(MenuVersion.status == "published")
        )
        == 0
    )


async def test_import_blocker_cannot_be_resolved_or_confirmed(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    created = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="blocked-preview"),
        json=import_payload(allergen_codes=["not-controlled"]),
    )
    body = created.json()
    finding = body["findings"][0]

    resolved = await auth_client.post(
        f"{url}/{body['id']}/findings/{finding['id']}/resolve",
        headers=mutation_headers(csrf, key="blocked-resolve"),
        json={
            "action": "confirm_legitimate",
            "target_entity_id": None,
            "comment": None,
            "expected_revision": 0,
        },
    )
    confirmed = await auth_client.post(
        f"{url}/{body['id']}/confirm",
        headers=mutation_headers(csrf, key="blocked-confirm"),
        json={"expected_revision": 0, "acknowledge_warnings": True},
    )

    assert created.status_code == 201
    assert finding["severity"] == "blocker"
    assert finding["allowed_actions"] == []
    assert resolved.status_code == 422
    assert resolved.json()["code"] == "FINDING_ACTION_NOT_ALLOWED"
    assert confirmed.status_code == 409
    assert confirmed.json()["code"] == "MENU_IMPORT_BLOCKED"
    assert await db_session.scalar(select(func.count()).select_from(MenuVersion)) == 0


async def test_import_requires_mfa_csrf_and_tenant_scope(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session, mfa_verified=False
    )
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    no_mfa = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="no-mfa-import"),
        json=import_payload(),
    )
    assert no_mfa.status_code == 403
    assert no_mfa.json()["code"] == "MFA_REQUIRED"

    auth_client.cookies.clear()
    organization_id, location_id, _admin_id, _csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    no_csrf = await auth_client.post(
        url,
        headers={"Origin": "https://frontend.test", "Idempotency-Key": "no-csrf-import"},
        json=import_payload(),
    )
    foreign = await auth_client.get(
        f"/api/v1/organizations/{uuid4()}/locations/{location_id}/menu-imports/{uuid4()}"
    )
    assert no_csrf.status_code == 403
    assert foreign.status_code == 404
    assert await db_session.scalar(select(func.count()).select_from(MenuImport)) == 0


def test_import_canonical_limits_are_server_authoritative() -> None:
    oversized = cast(dict[str, Any], import_payload())
    item = oversized["sections"][0]["categories"][0]["items"][0]
    item["description_uk"] = "я" * 4000
    category = oversized["sections"][0]["categories"][0]
    category["items"] = [
        {**item, "source_key": f"item-{index}", "stable_code": f"item-{index}", "position": index}
        for index in range(600)
    ]
    with pytest.raises(APIError, match="MENU_IMPORT_TOO_LARGE"):
        _canonical_payload(MenuImportCreate.model_validate(oversized))


async def test_import_openapi_excludes_raw_payload_and_actor_ids(
    auth_client: AsyncClient,
) -> None:
    document = (await auth_client.get("/openapi.json")).json()
    prefix = "/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    assert set(document["paths"][prefix]) == {"post"}
    assert set(document["paths"][f"{prefix}/{{import_id}}"]) == {"get"}
    assert set(document["paths"][f"{prefix}/{{import_id}}/confirm"]) == {"post"}
    serialized = str(document["components"]["schemas"])
    assert "source_payload" not in serialized
    assert "created_by_user_id" not in serialized
    assert "confirmed_by_user_id" not in serialized
