from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.private_storage import ObjectMetadata, UploadTarget
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers

FIXED_NOW = datetime(2030, 8, 27, 13, 0, tzinfo=UTC)


class FakePrivateStorage:
    def __init__(self) -> None:
        self.metadata: ObjectMetadata | None = None

    async def prepare_upload(
        self,
        *,
        object_key: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> UploadTarget:
        return UploadTarget(
            url="https://storage.test/upload",
            fields={"key": object_key, "Content-Type": mime_type},
        )

    async def inspect_object(self, *, object_key: str) -> ObjectMetadata | None:
        return self.metadata

    async def create_download_url(self, *, object_key: str, expires_seconds: int) -> str:
        return "https://storage.test/private-download"


async def test_admin_training_api_supports_draft_hierarchy_and_content(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}"
    versions_url = f"{base}/training-versions"

    create = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="training-draft"),
        json={"base_version_id": None},
    )
    replay = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="training-draft"),
        json={"base_version_id": None},
    )

    assert create.status_code == replay.status_code == 201
    assert create.json()["id"] == replay.json()["id"]
    assert create.json()["status"] == "draft"
    assert create.json()["revision"] == 0
    assert len(create.json()["modules"]) == 1
    version_id = UUID(create.json()["id"])
    module_id = UUID(create.json()["modules"][0]["id"])

    module = await auth_client.patch(
        f"{versions_url}/{version_id}/modules/{module_id}",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 0,
            "title_uk": "Меню ресторану",
            "description_uk": "Базові знання",
            "required": True,
        },
    )
    assert module.status_code == 200
    assert module.json()["revision"] == 1

    lesson = await auth_client.post(
        f"{versions_url}/{version_id}/modules/{module_id}/lessons",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 1,
            "title_uk": "Супи",
            "description_uk": None,
            "required": True,
            "estimated_minutes": 8,
        },
    )
    assert lesson.status_code == 200
    lesson_id = UUID(lesson.json()["lesson"]["id"])
    assert lesson.json()["revision"] == 2

    block = await auth_client.post(
        f"{versions_url}/{version_id}/lessons/{lesson_id}/content-blocks",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 2,
            "type": "text",
            "payload": {"text_uk": "Головне про супи"},
        },
    )
    assert block.status_code == 200
    block_id = UUID(block.json()["content_block"]["id"])
    assert block.json()["revision"] == 3

    conflict = await auth_client.patch(
        f"{versions_url}/{version_id}/content-blocks/{block_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 2, "payload": {"text_uk": "Застаріла зміна"}},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "REVISION_CONFLICT"

    block_update = await auth_client.patch(
        f"{versions_url}/{version_id}/content-blocks/{block_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 3, "payload": {"text_uk": "Оновлено про супи"}},
    )
    second_lesson = await auth_client.post(
        f"{versions_url}/{version_id}/modules/{module_id}/lessons",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 4,
            "title_uk": "Салати",
            "description_uk": None,
            "required": False,
            "estimated_minutes": 5,
        },
    )
    second_lesson_id = UUID(second_lesson.json()["lesson"]["id"])
    lessons_reorder = await auth_client.post(
        f"{versions_url}/{version_id}/modules/{module_id}/lessons/reorder",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 5,
            "ordered_ids": [str(second_lesson_id), str(lesson_id)],
        },
    )
    second_block = await auth_client.post(
        f"{versions_url}/{version_id}/lessons/{lesson_id}/content-blocks",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 6,
            "type": "callout",
            "payload": {"tone": "tip", "title_uk": None, "text_uk": "Порада"},
        },
    )
    second_block_id = UUID(second_block.json()["content_block"]["id"])
    blocks_reorder = await auth_client.post(
        f"{versions_url}/{version_id}/lessons/{lesson_id}/content-blocks/reorder",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 7,
            "ordered_ids": [str(second_block_id), str(block_id)],
        },
    )
    block_delete = await auth_client.delete(
        f"{versions_url}/{version_id}/content-blocks/{second_block_id}",
        headers=mutation_headers(csrf),
        params={"expected_revision": 8},
    )
    lesson_update = await auth_client.patch(
        f"{versions_url}/{version_id}/lessons/{lesson_id}",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 9,
            "title_uk": "Супи та бульйони",
            "description_uk": None,
            "required": True,
            "estimated_minutes": 9,
        },
    )
    lesson_delete = await auth_client.delete(
        f"{versions_url}/{version_id}/lessons/{second_lesson_id}",
        headers=mutation_headers(csrf),
        params={"expected_revision": 10},
    )

    assert block_update.json()["revision"] == 4
    assert second_lesson.status_code == 200
    assert lessons_reorder.json()["ordered_ids"] == [str(second_lesson_id), str(lesson_id)]
    assert blocks_reorder.json()["ordered_ids"] == [str(second_block_id), str(block_id)]
    assert block_delete.json()["revision"] == 9
    assert lesson_update.json()["lesson"]["title_uk"] == "Супи та бульйони"
    assert lesson_delete.json()["revision"] == 11

    detail = await auth_client.get(f"{versions_url}/{version_id}")
    navigation = await auth_client.get(versions_url)
    assert detail.status_code == navigation.status_code == 200
    assert detail.json()["modules"][0]["lessons"][0]["content_blocks"][0]["id"] == str(block_id)
    assert navigation.json()["draft"]["id"] == str(version_id)


async def test_admin_training_asset_api_keeps_storage_private(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    storage = FakePrivateStorage()
    auth_app.state.private_storage = storage
    base = f"/api/v1/organizations/{organization_id}/locations/{location_id}/assets"
    sha256 = "a" * 64

    intent = await auth_client.post(
        f"{base}/upload-intents",
        headers=mutation_headers(csrf, key="training-asset-intent"),
        json={
            "file_name": "dish.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": 120,
            "sha256": sha256,
        },
    )
    assert intent.status_code == 201
    asset_id = UUID(intent.json()["asset_id"])
    assert intent.json()["upload_url"] == "https://storage.test/upload"
    assert "object_key" not in intent.json()

    storage.metadata = ObjectMetadata(
        mime_type="image/jpeg",
        size_bytes=120,
        sha256=sha256,
    )
    complete = await auth_client.post(
        f"{base}/{asset_id}/complete",
        headers=mutation_headers(csrf, key="training-asset-complete"),
        json={"sha256": sha256},
    )
    access = await auth_client.get(f"{base}/{asset_id}/access")

    assert complete.status_code == 200
    assert complete.json()["status"] == "ready"
    assert "object_key" not in complete.json()
    assert access.status_code == 200
    assert access.json() == {"url": "https://storage.test/private-download", "expires_in": 300}

    archived = await auth_client.delete(
        f"{base}/{asset_id}",
        headers=mutation_headers(csrf),
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


async def test_admin_training_api_requires_csrf_mfa_and_same_tenant(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    no_mfa = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="training-no-mfa"),
        json={"base_version_id": None},
    )
    assert no_mfa.status_code == 403
    assert no_mfa.json()["code"] == "MFA_REQUIRED"

    auth_client.cookies.clear()
    organization_id, location_id, _admin_id, _csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
    )
    missing_csrf = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions",
        headers={"Origin": "https://frontend.test", "Idempotency-Key": "missing-csrf"},
        json={"base_version_id": None},
    )
    foreign = await auth_client.get(
        f"/api/v1/organizations/{uuid4()}/locations/{location_id}/training-versions"
    )
    foreign_location = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/locations/{uuid4()}/training-versions"
    )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_INVALID"
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "RESOURCE_NOT_FOUND"
    assert foreign_location.status_code == 404
    assert foreign_location.json()["code"] == "RESOURCE_NOT_FOUND"
