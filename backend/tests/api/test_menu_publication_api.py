import asyncio
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, MenuItemVersion, MenuItemVersionTranslation, MenuVersion
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_menu_import_api import import_payload


async def arrange_ready_draft(
    client: AsyncClient,
    *,
    organization_id: UUID,
    location_id: UUID,
    csrf: str,
    key_prefix: str,
) -> dict[str, object]:
    imports_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-imports"
    preview = await client.post(
        imports_url,
        headers=mutation_headers(csrf, key=f"{key_prefix}-preview"),
        json=import_payload(),
    )
    assert preview.status_code == 201
    confirm = await client.post(
        f"{imports_url}/{preview.json()['id']}/confirm",
        headers=mutation_headers(csrf, key=f"{key_prefix}-confirm"),
        json={"expected_revision": 0, "acknowledge_warnings": False},
    )
    assert confirm.status_code == 200
    return cast(dict[str, object], confirm.json()["draft"])


async def test_readiness_and_publish_are_idempotent_with_zero_applicability(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="first-publish",
    )
    version_id = UUID(str(draft["id"]))
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions/"
        f"{version_id}"
    )
    readiness = await auth_client.get(f"{base}/readiness")
    headers = mutation_headers(csrf, key="publish-ready-menu")
    published = await auth_client.post(
        f"{base}/publish",
        headers=headers,
        json={"expected_revision": draft["revision"]},
    )
    replay = await auth_client.post(
        f"{base}/publish",
        headers=headers,
        json={"expected_revision": draft["revision"]},
    )

    assert readiness.status_code == 200
    assert readiness.json()["can_publish"] is True
    assert readiness.json()["required_training_asset_count"] == 0
    assert readiness.json()["ready_training_asset_count"] == 0
    assert readiness.json()["applicable_training_content_count"] == 0
    assert published.status_code == replay.status_code == 200
    assert published.json() == replay.json()
    assert published.json()["published"]["status"] == "published"
    assert published.json()["diff_counts"]["added"] == 1
    assert published.json()["applicability"] == {
        "published_content_count": 0,
        "assignment_count": 0,
        "notification_count": 0,
    }
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "menu_version_published")
        )
        == 1
    )


async def test_second_publication_atomically_archives_previous_snapshot(
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
        key_prefix="snapshot-first",
    )
    versions_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions"
    first_id = UUID(str(first_draft["id"]))
    first_publish = await auth_client.post(
        f"{versions_url}/{first_id}/publish",
        headers=mutation_headers(csrf, key="snapshot-first-publish"),
        json={"expected_revision": first_draft["revision"]},
    )
    assert first_publish.status_code == 200

    second_draft = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="snapshot-second-draft"),
        json={"copy_from_version_id": None},
    )
    second_id = UUID(second_draft.json()["id"])
    second_publish = await auth_client.post(
        f"{versions_url}/{second_id}/publish",
        headers=mutation_headers(csrf, key="snapshot-second-publish"),
        json={"expected_revision": second_draft.json()["revision"]},
    )

    assert second_publish.status_code == 200
    assert second_publish.json()["previous_published_version_id"] == str(first_id)
    assert second_publish.json()["diff_counts"]["unchanged"] == 1
    db_session.expire_all()
    assert (await db_session.get_one(MenuVersion, first_id)).status == "archived"
    assert (await db_session.get_one(MenuVersion, second_id)).status == "published"
    assert (
        await db_session.scalar(
            select(func.count()).select_from(MenuVersion).where(MenuVersion.status == "published")
        )
        == 1
    )


@pytest.mark.parametrize("problem", ["facts", "translation", "revision"])
async def test_publication_rejection_preserves_draft_and_audit(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession, problem: str
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix=f"blocked-{problem}",
    )
    version_id = UUID(str(draft["id"]))
    if problem == "facts":
        item = await db_session.scalar(
            select(MenuItemVersion).where(MenuItemVersion.menu_version_id == version_id)
        )
        assert item is not None
        item.component_data_status = "unknown"
    elif problem == "translation":
        translation = await db_session.scalar(
            select(MenuItemVersionTranslation).where(
                MenuItemVersionTranslation.menu_version_id == version_id,
                MenuItemVersionTranslation.locale == "uk",
            )
        )
        assert translation is not None
        await db_session.delete(translation)
    await db_session.commit()
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions/"
        f"{version_id}"
    )
    before = await auth_client.get(base)
    readiness = await auth_client.get(f"{base}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["can_publish"] is (problem == "revision")
    if problem != "revision":
        expected_blocker = "FACTS_UNCONFIRMED" if problem == "facts" else "UA_CONTENT_NOT_READY"
        assert expected_blocker in {issue["code"] for issue in readiness.json()["blocking_errors"]}
    audit_before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = await auth_client.post(
        f"{base}/publish",
        headers=mutation_headers(csrf, key=f"deny-{problem}"),
        json={"expected_revision": 999 if problem == "revision" else draft["revision"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == (
        "REVISION_CONFLICT" if problem == "revision" else "MENU_NOT_READY"
    )
    after = await auth_client.get(base)
    assert before.json() == after.json()
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_before
    assert (
        await db_session.scalar(
            select(func.count()).select_from(MenuVersion).where(MenuVersion.status == "published")
        )
        == 0
    )


async def test_not_ready_publish_has_no_partial_effect_and_different_key_race_has_one_winner(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    versions_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions"
    empty = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="empty-draft"),
        json={"copy_from_version_id": None},
    )
    empty_id = UUID(empty.json()["id"])
    blocked = await auth_client.post(
        f"{versions_url}/{empty_id}/publish",
        headers=mutation_headers(csrf, key="empty-publish"),
        json={"expected_revision": 0},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "MENU_NOT_READY"
    assert (
        await db_session.scalar(
            select(func.count()).select_from(MenuVersion).where(MenuVersion.status == "published")
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "menu_version_published")
        )
        == 0
    )

    # The empty Draft is deliberately populated through a second import Confirm.
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="race",
    )
    version_id = UUID(str(draft["id"]))
    publish_url = f"{versions_url}/{version_id}/publish"
    first, second = await asyncio.gather(
        auth_client.post(
            publish_url,
            headers=mutation_headers(csrf, key="race-publish-a"),
            json={"expected_revision": draft["revision"]},
        ),
        auth_client.post(
            publish_url,
            headers=mutation_headers(csrf, key="race-publish-b"),
            json={"expected_revision": draft["revision"]},
        ),
    )
    assert sorted((first.status_code, second.status_code)) == [200, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json()["code"] == "REVISION_CONFLICT"
    assert (
        await db_session.scalar(
            select(func.count()).select_from(MenuVersion).where(MenuVersion.status == "published")
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "menu_version_published")
        )
        == 1
    )


@pytest.mark.parametrize(
    "production,missing_translation", [(False, False), (True, False), (False, True)]
)
async def test_explicit_demo_publication_preserves_unknown_facts_and_other_gates(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    production: bool,
    missing_translation: bool,
) -> None:
    organization_id, location_id, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    draft = await arrange_ready_draft(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="demo-facts",
    )
    version_id = UUID(str(draft["id"]))
    item = await db_session.scalar(
        select(MenuItemVersion).where(MenuItemVersion.menu_version_id == version_id)
    )
    assert item is not None
    item.component_data_status = "unknown"
    if missing_translation:
        translation = await db_session.scalar(
            select(MenuItemVersionTranslation).where(
                MenuItemVersionTranslation.menu_version_id == version_id,
                MenuItemVersionTranslation.locale == "uk",
            )
        )
        assert translation is not None
        await db_session.delete(translation)
    item_version_id = item.id
    stable_item_id = str(item.menu_item_id)
    await db_session.commit()
    original_env = auth_app.state.settings.app_env
    auth_app.state.settings.app_env = "production" if production else "test"
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}"
        f"/menu-versions/{version_id}"
    )
    try:
        readiness = (await auth_client.get(f"{base}/readiness")).json()
        assert readiness["can_publish"] is False
        if missing_translation:
            issue = next(
                row for row in readiness["blocking_errors"] if row["code"] == "UA_CONTENT_NOT_READY"
            )
            assert issue["entity_id"] == stable_item_id
        assert readiness.get("demo_publication_allowed") is (
            not production and not missing_translation
        )
        ordinary = await auth_client.post(
            f"{base}/publish",
            headers=mutation_headers(csrf, key="demo-strict"),
            json={"expected_revision": draft["revision"]},
        )
        assert ordinary.status_code == 409
        headers = mutation_headers(csrf, key="demo-explicit")
        payload = {"expected_revision": draft["revision"], "demo_with_unknown_facts": True}
        response = await auth_client.post(f"{base}/publish", headers=headers, json=payload)
        assert response.status_code == (403 if production else 409 if missing_translation else 200)
        if not production and not missing_translation:
            replay = await auth_client.post(f"{base}/publish", headers=headers, json=payload)
            assert replay.status_code == 200
            assert replay.json() == response.json()
            mismatch = await auth_client.post(
                f"{base}/publish", headers=headers, json={"expected_revision": draft["revision"]}
            )
            assert mismatch.status_code == 409
            assert mismatch.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
        db_session.expire_all()
        saved = await db_session.get_one(MenuItemVersion, item_version_id)
        assert saved.component_data_status == "unknown"
        audit = await db_session.scalar(
            select(AuditEvent).where(AuditEvent.action == "menu_version_published")
        )
        if production or missing_translation:
            assert audit is None
        else:
            assert audit is not None and audit.new_values is not None
            assert audit.new_values["demo_with_unknown_facts"] is True
    finally:
        auth_app.state.settings.app_env = original_env
