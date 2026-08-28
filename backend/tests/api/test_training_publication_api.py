import asyncio
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, TrainingVersion
from app.services import training_publication
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.api.test_menu_publication_api import arrange_ready_draft


async def publish_menu(
    client: AsyncClient,
    *,
    organization_id: UUID,
    location_id: UUID,
    csrf: str,
    key_prefix: str,
) -> None:
    draft = await arrange_ready_draft(
        client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix=key_prefix,
    )
    response = await client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/menu-versions/"
        f"{draft['id']}/publish",
        headers=mutation_headers(csrf, key=f"{key_prefix}-publish"),
        json={"expected_revision": draft["revision"]},
    )
    assert response.status_code == 200


async def arrange_ready_training(
    client: AsyncClient,
    *,
    organization_id: UUID,
    location_id: UUID,
    csrf: str,
    key_prefix: str,
    base_version_id: UUID | None = None,
) -> dict[str, object]:
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    draft = await client.post(
        versions_url,
        headers=mutation_headers(csrf, key=f"{key_prefix}-draft"),
        json={"base_version_id": str(base_version_id) if base_version_id is not None else None},
    )
    assert draft.status_code == 201
    detail = draft.json()
    if base_version_id is not None:
        return cast(dict[str, object], detail)
    version_id = detail["id"]
    module_id = detail["modules"][0]["id"]
    lesson = await client.post(
        f"{versions_url}/{version_id}/modules/{module_id}/lessons",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 0,
            "title_uk": "Основи меню",
            "description_uk": None,
            "required": True,
            "estimated_minutes": 5,
        },
    )
    assert lesson.status_code == 200
    lesson_id = lesson.json()["lesson"]["id"]
    block = await client.post(
        f"{versions_url}/{version_id}/lessons/{lesson_id}/content-blocks",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 1,
            "type": "text",
            "payload": {"text_uk": "Прочитайте правила подачі."},
        },
    )
    assert block.status_code == 200
    return cast(
        dict[str, object],
        (await client.get(f"{versions_url}/{version_id}")).json(),
    )


async def test_training_readiness_and_publish_are_idempotent_with_zero_slice4_effects(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-menu",
    )
    draft = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-first",
    )
    version_id = UUID(str(draft["id"]))
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions/"
        f"{version_id}"
    )
    readiness = await auth_client.get(f"{base}/readiness")
    headers = mutation_headers(csrf, key="training-publish")
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
    assert readiness.json()["blocking_errors"] == []
    assert {warning["code"] for warning in readiness.json()["warnings"]} == {
        "EN_TRANSLATION_PENDING"
    }
    assert readiness.json()["counts"] == {
        "module_count": 1,
        "lesson_count": 1,
        "required_lesson_count": 1,
        "content_block_count": 1,
        "required_asset_count": 0,
        "ready_asset_count": 0,
        "menu_item_link_count": 0,
    }
    assert published.status_code == replay.status_code == 200
    assert published.json() == replay.json()
    assert published.json()["published"]["status"] == "published"
    assert published.json()["employee_reference_switched"] is True
    assert published.json()["previous_published_version_id"] is None
    assert published.json()["assignment_count"] == 0
    assert published.json()["completion_count"] == 0
    assert published.json()["progress_count"] == 0
    assert published.json()["rollout_count"] == 0
    assert published.json()["notification_count"] == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_published")
        )
        == 1
    )


async def test_training_publish_blocks_invalid_readiness_without_partial_effect(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    draft = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="blocked-training"),
        json={"base_version_id": None},
    )
    version_id = UUID(draft.json()["id"])
    readiness = await auth_client.get(f"{versions_url}/{version_id}/readiness")
    blocked = await auth_client.post(
        f"{versions_url}/{version_id}/publish",
        headers=mutation_headers(csrf, key="blocked-training-publish"),
        json={"expected_revision": 0},
    )

    assert readiness.status_code == 200
    assert readiness.json()["can_publish"] is False
    assert [issue["code"] for issue in readiness.json()["blocking_errors"]] == sorted(
        ["MENU_DEPENDENCY_INVALID", "REQUIRED_LESSON_MISSING"]
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "TRAINING_NOT_READY"
    db_session.expire_all()
    assert (await db_session.get_one(TrainingVersion, version_id)).status == "draft"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_published")
        )
        == 0
    )


async def test_training_publication_archives_previous_and_different_key_race_has_one_winner(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-snapshot-menu",
    )
    first = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-snapshot-first",
    )
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    first_id = UUID(str(first["id"]))
    first_publish = await auth_client.post(
        f"{versions_url}/{first_id}/publish",
        headers=mutation_headers(csrf, key="training-snapshot-first-publish"),
        json={"expected_revision": first["revision"]},
    )
    assert first_publish.status_code == 200

    second = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-snapshot-second",
        base_version_id=first_id,
    )
    second_id = UUID(str(second["id"]))
    publish_url = f"{versions_url}/{second_id}/publish"
    winner, loser = await asyncio.gather(
        auth_client.post(
            publish_url,
            headers=mutation_headers(csrf, key="training-race-a"),
            json={"expected_revision": second["revision"]},
        ),
        auth_client.post(
            publish_url,
            headers=mutation_headers(csrf, key="training-race-b"),
            json={"expected_revision": second["revision"]},
        ),
    )
    responses = [winner, loser]
    assert sorted(response.status_code for response in responses) == [200, 409]
    failure = next(response for response in responses if response.status_code == 409)
    success = next(response for response in responses if response.status_code == 200)
    assert failure.json()["code"] == "REVISION_CONFLICT"
    assert success.json()["previous_published_version_id"] == str(first_id)

    db_session.expire_all()
    assert (await db_session.get_one(TrainingVersion, first_id)).status == "archived"
    assert (await db_session.get_one(TrainingVersion, second_id)).status == "published"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(TrainingVersion)
            .where(TrainingVersion.status == "published")
        )
        == 1
    )


async def test_training_publish_revalidates_current_menu_dependency(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-stale-menu-first",
    )
    training = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-stale-dependency",
    )
    version_id = UUID(str(training["id"]))
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    before = await auth_client.get(f"{versions_url}/{version_id}/readiness")
    assert before.json()["can_publish"] is True

    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-stale-menu-second",
    )
    after = await auth_client.get(f"{versions_url}/{version_id}/readiness")
    blocked = await auth_client.post(
        f"{versions_url}/{version_id}/publish",
        headers=mutation_headers(csrf, key="training-stale-publish"),
        json={"expected_revision": training["revision"]},
    )

    assert after.json()["can_publish"] is False
    assert "MENU_DEPENDENCY_INVALID" in {issue["code"] for issue in after.json()["blocking_errors"]}
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "TRAINING_NOT_READY"


async def test_training_publish_forced_failure_rolls_back_atomic_switch(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-rollback-menu",
    )
    first = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-rollback-first",
    )
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    first_id = UUID(str(first["id"]))
    assert (
        await auth_client.post(
            f"{versions_url}/{first_id}/publish",
            headers=mutation_headers(csrf, key="training-rollback-first-publish"),
            json={"expected_revision": first["revision"]},
        )
    ).status_code == 200
    second = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="training-rollback-second",
        base_version_id=first_id,
    )
    second_id = UUID(str(second["id"]))

    async def fail_reservation(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced publication failure")

    monkeypatch.setattr(training_publication, "reserve_idempotency", fail_reservation)
    db_session.expire_all()
    second_revision = second["revision"]
    assert isinstance(second_revision, int)
    with pytest.raises(RuntimeError, match="forced publication failure"):
        await training_publication.publish_training_version(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            version_id=second_id,
            actor_user_id=admin_id,
            request_id=uuid4(),
            expected_revision=second_revision,
            idempotency_key="training-forced-rollback",
            now=FIXED_NOW,
        )

    db_session.expire_all()
    assert (await db_session.get_one(TrainingVersion, first_id)).status == "published"
    assert (await db_session.get_one(TrainingVersion, second_id)).status == "draft"
