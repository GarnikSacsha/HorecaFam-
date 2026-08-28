from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.private_storage import ObjectMetadata
from tests.api.test_employee_menu_api import attach_employee
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_training_admin_api import FakePrivateStorage
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu


def first_lesson_id(detail: dict[str, object]) -> UUID:
    modules = detail["modules"]
    assert isinstance(modules, list) and modules
    module = modules[0]
    assert isinstance(module, dict)
    lessons = module["lessons"]
    assert isinstance(lessons, list) and lessons
    lesson = lessons[0]
    assert isinstance(lesson, dict)
    return UUID(str(lesson["id"]))


async def publish_training(
    client: AsyncClient,
    *,
    organization_id: UUID,
    location_id: UUID,
    csrf: str,
    key_prefix: str,
) -> dict[str, object]:
    draft = await arrange_ready_training(
        client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix=key_prefix,
    )
    response = await client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions/"
        f"{draft['id']}/publish",
        headers=mutation_headers(csrf, key=f"{key_prefix}-publish"),
        json={"expected_revision": draft["revision"]},
    )
    assert response.status_code == 200
    return draft


async def test_employee_reads_only_current_published_training_with_entity_fallback(
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
        key_prefix="employee-training-menu",
    )
    published = await publish_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="employee-training-current",
    )
    published_id = UUID(str(published["id"]))
    published_lesson_id = first_lesson_id(published)
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )

    hidden_draft = await auth_client.post(
        versions_url,
        headers=mutation_headers(csrf, key="employee-training-hidden-draft"),
        json={"base_version_id": str(published_id)},
    )
    hidden_module_id = UUID(hidden_draft.json()["modules"][0]["id"])
    hidden_lesson = await auth_client.post(
        f"{versions_url}/{hidden_draft.json()['id']}/modules/{hidden_module_id}/lessons",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": 0,
            "title_uk": "Лише в чернетці",
            "description_uk": None,
            "required": False,
            "estimated_minutes": 3,
        },
    )
    hidden_lesson_id = UUID(hidden_lesson.json()["lesson"]["id"])

    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        preferred_locale="en",
    )
    listing = await auth_client.get("/api/v1/me/training", params={"locale": "en"})
    module_id = UUID(listing.json()["modules"][0]["id"])
    module = await auth_client.get(
        f"/api/v1/me/training/modules/{module_id}", params={"locale": "en"}
    )
    lesson = await auth_client.get(
        f"/api/v1/me/training/lessons/{published_lesson_id}", params={"locale": "en"}
    )
    hidden = await auth_client.get(f"/api/v1/me/training/lessons/{hidden_lesson_id}")

    assert listing.status_code == module.status_code == lesson.status_code == 200
    assert listing.json()["training"]["id"] != str(published_id)
    assert listing.json()["modules"][0]["content_locale"] == "uk"
    assert listing.json()["modules"][0]["translation_fallback"] is True
    assert module.json()["lessons"][0]["id"] == str(published_lesson_id)
    assert module.json()["lessons"][0]["translation_fallback"] is True
    assert lesson.json()["content_blocks"][0]["payload"] == {
        "text_uk": "Прочитайте правила подачі."
    }
    assert lesson.json()["content_blocks"][0]["translation_fallback"] is True
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"
    for forbidden in (
        "revision",
        "base_version_id",
        "object_key",
        "sha256",
        "created_by_user_id",
        "published_by_user_id",
        "training_version_id",
    ):
        assert forbidden not in listing.text
        assert forbidden not in module.text
        assert forbidden not in lesson.text


async def test_employee_training_empty_state_and_active_profile_boundary(
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
    empty = await auth_client.get("/api/v1/me/training")
    assert empty.status_code == 200
    assert empty.json() == {
        "training": None,
        "modules": [],
        "content_locale": "uk",
        "translation_fallback": False,
    }

    auth_client.cookies.clear()
    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        status="disabled",
    )
    denied = await auth_client.get("/api/v1/me/training")
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"


async def test_employee_asset_access_requires_current_published_training_link(
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
        key_prefix="employee-training-asset-menu",
    )
    draft = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="employee-training-asset",
    )
    storage = FakePrivateStorage()
    auth_app.state.private_storage = storage
    assets_url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/assets"

    async def ready_asset(key_prefix: str, sha256: str) -> UUID:
        intent = await auth_client.post(
            f"{assets_url}/upload-intents",
            headers=mutation_headers(csrf, key=f"{key_prefix}-intent"),
            json={
                "file_name": f"{key_prefix}.jpg",
                "mime_type": "image/jpeg",
                "size_bytes": 120,
                "sha256": sha256,
            },
        )
        asset_id = UUID(intent.json()["asset_id"])
        storage.metadata = ObjectMetadata(
            mime_type="image/jpeg",
            size_bytes=120,
            sha256=sha256,
        )
        complete = await auth_client.post(
            f"{assets_url}/{asset_id}/complete",
            headers=mutation_headers(csrf, key=f"{key_prefix}-complete"),
            json={"sha256": sha256},
        )
        assert complete.status_code == 200
        return asset_id

    linked_asset_id = await ready_asset("linked", "a" * 64)
    unlinked_asset_id = await ready_asset("unlinked", "b" * 64)
    version_id = UUID(str(draft["id"]))
    lesson_id = first_lesson_id(draft)
    image = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions/"
        f"{version_id}/lessons/{lesson_id}/content-blocks",
        headers=mutation_headers(csrf),
        json={
            "expected_revision": draft["revision"],
            "type": "image",
            "payload": {
                "asset_id": str(linked_asset_id),
                "alt_uk": "Подача страви",
                "caption_uk": None,
            },
        },
    )
    assert image.status_code == 200
    publish = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions/"
        f"{version_id}/publish",
        headers=mutation_headers(csrf, key="employee-training-asset-publish"),
        json={"expected_revision": image.json()["revision"]},
    )
    assert publish.status_code == 200

    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    lesson = await auth_client.get(f"/api/v1/me/training/lessons/{lesson_id}")
    linked = await auth_client.get(f"/api/v1/me/training/assets/{linked_asset_id}/access")
    unlinked = await auth_client.get(f"/api/v1/me/training/assets/{unlinked_asset_id}/access")
    foreign = await auth_client.get(f"/api/v1/me/training/assets/{uuid4()}/access")

    assert lesson.status_code == linked.status_code == 200
    image_block = next(
        block for block in lesson.json()["content_blocks"] if block["type"] == "image"
    )
    assert image_block["payload"]["asset_id"] == str(linked_asset_id)
    assert linked.json() == {"url": "https://storage.test/private-download", "expires_in": 300}
    assert unlinked.status_code == foreign.status_code == 404


async def test_employee_training_openapi_is_read_only_and_has_no_completion_route(
    auth_client: AsyncClient,
) -> None:
    document = (await auth_client.get("/openapi.json")).json()
    paths = document["paths"]
    assert set(paths["/api/v1/me/training"]) == {"get"}
    assert set(paths["/api/v1/me/training/modules/{module_id}"]) == {"get"}
    assert set(paths["/api/v1/me/training/lessons/{lesson_id}"]) == {"get"}
    assert set(paths["/api/v1/me/training/assets/{asset_id}/access"]) == {"get"}
    assert "/api/v1/me/training/lessons/{lesson_id}/complete" not in paths
    employee_schemas = {
        key: value
        for key, value in document["components"]["schemas"].items()
        if key.startswith("EmployeeTraining")
    }
    serialized = str(employee_schemas)
    for forbidden in ("revision", "object_key", "sha256", "base_version_id"):
        assert forbidden not in serialized
