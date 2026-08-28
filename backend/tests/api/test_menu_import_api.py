import asyncio
from copy import deepcopy
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import MenuImport, MenuVersion, Organization
from app.schemas.menu import MenuImportCreate
from app.services.menu_imports import _canonical_payload
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.factories.identity import make_location


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


async def arrange_review_import(
    client: AsyncClient,
    *,
    organization_id: UUID,
    location_id: UUID,
    csrf: str,
    key_prefix: str,
) -> tuple[str, dict[str, object]]:
    imports_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    baseline = await client.post(
        imports_url,
        headers=mutation_headers(csrf, key=f"{key_prefix}-baseline-preview"),
        json=import_payload(),
    )
    assert baseline.status_code == 201
    confirmed = await client.post(
        f"{imports_url}/{baseline.json()['id']}/confirm",
        headers=mutation_headers(csrf, key=f"{key_prefix}-baseline-confirm"),
        json={"expected_revision": 0, "acknowledge_warnings": False},
    )
    assert confirmed.status_code == 200
    draft = confirmed.json()["draft"]
    published = await client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions/"
        f"{draft['id']}/publish",
        headers=mutation_headers(csrf, key=f"{key_prefix}-baseline-publish"),
        json={"expected_revision": draft["revision"]},
    )
    assert published.status_code == 200

    changed_payload = deepcopy(import_payload())
    sections = cast(list[dict[str, Any]], changed_payload["sections"])
    item = cast(dict[str, Any], sections[0]["categories"][0]["items"][0])
    item["component_data_status"] = "confirmed_present"
    item["components"] = [
        {
            "stable_code": f"component-{key_prefix}",
            "name_uk": "Новий компонент",
            "optional": False,
            "position": 0,
        }
    ]
    review = await client.post(
        imports_url,
        headers=mutation_headers(csrf, key=f"{key_prefix}-review-preview"),
        json=changed_payload,
    )
    assert review.status_code == 201
    assert review.json()["review_count"] == 1
    assert review.json()["findings"][0]["code"] == "CRITICAL_FACT_CHANGE"
    return imports_url, cast(dict[str, object], review.json())


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
    assert resolved.json()["code"] == "IMPORT_FINDING_RESOLUTION_INVALID"
    assert confirmed.status_code == 409
    assert confirmed.json()["code"] == "IMPORT_NOT_READY"
    assert await db_session.scalar(select(func.count()).select_from(MenuVersion)) == 0


async def test_import_resolution_and_confirm_concurrency_are_retry_safe(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, first_location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    organization = await db_session.get_one(Organization, organization_id)
    second_location = make_location(organization, name="Second import concurrency location")
    db_session.add(second_location)
    await db_session.commit()

    first_url, first_review = await arrange_review_import(
        auth_client,
        organization_id=organization_id,
        location_id=first_location_id,
        csrf=csrf,
        key_prefix="same-key",
    )
    second_url, second_review = await arrange_review_import(
        auth_client,
        organization_id=organization_id,
        location_id=second_location.id,
        csrf=csrf,
        key_prefix="different-key",
    )

    async def resolve(
        url: str,
        review: dict[str, object],
        *,
        key: str,
    ) -> Any:
        findings = cast(list[dict[str, object]], review["findings"])
        return await auth_client.post(
            f"{url}/{review['id']}/findings/{findings[0]['id']}/resolve",
            headers=mutation_headers(csrf, key=key),
            json={
                "action": "confirm_critical_change",
                "target_entity_id": None,
                "comment": "Reviewed",
                "expected_revision": 0,
            },
        )

    same_key_resolutions = await asyncio.gather(
        resolve(first_url, first_review, key="resolve-same-key"),
        resolve(first_url, first_review, key="resolve-same-key"),
    )
    assert [response.status_code for response in same_key_resolutions] == [200, 200]
    assert {response.json()["review_revision"] for response in same_key_resolutions} == {1}

    different_key_resolutions = await asyncio.gather(
        resolve(second_url, second_review, key="resolve-key-a"),
        resolve(second_url, second_review, key="resolve-key-b"),
    )
    assert sorted(response.status_code for response in different_key_resolutions) == [200, 409]
    resolution_loser = next(
        response for response in different_key_resolutions if response.status_code == 409
    )
    assert resolution_loser.json()["code"] == "REVISION_CONFLICT"

    async def confirm(url: str, review: dict[str, object], *, key: str) -> Any:
        return await auth_client.post(
            f"{url}/{review['id']}/confirm",
            headers=mutation_headers(csrf, key=key),
            json={"expected_revision": 1, "acknowledge_warnings": False},
        )

    same_key_confirms = await asyncio.gather(
        confirm(first_url, first_review, key="confirm-same-key"),
        confirm(first_url, first_review, key="confirm-same-key"),
    )
    assert [response.status_code for response in same_key_confirms] == [200, 200]
    assert len({response.json()["draft"]["id"] for response in same_key_confirms}) == 1

    different_key_confirms = await asyncio.gather(
        confirm(second_url, second_review, key="confirm-key-a"),
        confirm(second_url, second_review, key="confirm-key-b"),
    )
    assert sorted(response.status_code for response in different_key_confirms) == [200, 409]
    confirm_loser = next(
        response for response in different_key_confirms if response.status_code == 409
    )
    assert confirm_loser.json()["code"] == "IMPORT_NOT_READY"


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
