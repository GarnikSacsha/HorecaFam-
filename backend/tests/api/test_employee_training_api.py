from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EmployeeProfile,
    LessonVersion,
    OrganizationMembership,
    Training,
    TrainingAssignment,
    TrainingModuleVersion,
    TrainingVersion,
)
from app.services.private_storage import ObjectMetadata
from tests.api.test_employee_menu_api import attach_employee
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_training_admin_api import FakePrivateStorage
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu
from tests.factories.training import make_lesson_completion, make_training_assignment


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


async def test_employee_training_home_is_assignment_scoped_with_derived_progress(
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
        key_prefix="assignment-home-menu",
    )
    published = await publish_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="assignment-home-training",
    )
    version = await db_session.get_one(TrainingVersion, UUID(str(published["id"])))
    training = await db_session.get_one(Training, version.training_id)
    user_id = await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    profile = await db_session.scalar(
        select(EmployeeProfile)
        .join(OrganizationMembership)
        .where(OrganizationMembership.user_id == user_id)
    )
    assert profile is not None
    assignment = make_training_assignment(profile, training, version)
    db_session.add(assignment)
    await db_session.commit()

    response = await auth_client.get("/api/v1/me/training")

    assert response.status_code == 200
    assert response.json()["assignment"] == {
        "id": str(assignment.id),
        "status": "assigned",
        "assigned_at": assignment.assigned_at.isoformat().replace("+00:00", "Z"),
        "started_at": None,
        "completed_at": None,
    }
    assert response.json()["progress"] == {
        "required_lesson_count": 1,
        "completed_required_lesson_count": 0,
        "percentage": 0,
        "is_complete": False,
    }
    assert response.json()["next_action"] == "open_lesson"

    lesson_version = await db_session.scalar(
        select(LessonVersion)
        .join(TrainingModuleVersion)
        .where(TrainingModuleVersion.training_version_id == version.id)
    )
    assert lesson_version is not None
    db_session.add(make_lesson_completion(assignment, lesson_version, user_id))
    await db_session.commit()

    completed_home = await auth_client.get("/api/v1/me/training")
    completed_lesson = await auth_client.get(
        f"/api/v1/me/training/lessons/{lesson_version.lesson_id}"
    )
    assert completed_home.json()["progress"] == {
        "required_lesson_count": 1,
        "completed_required_lesson_count": 1,
        "percentage": 100,
        "is_complete": True,
    }
    assert completed_home.json()["next_action"] == "review_training"
    assert completed_lesson.json()["completed"] is True


async def attach_training_assignment(
    db: AsyncSession,
    *,
    user_id: UUID,
    version_id: UUID,
) -> TrainingAssignment:
    profile = await db.scalar(
        select(EmployeeProfile)
        .join(OrganizationMembership)
        .where(OrganizationMembership.user_id == user_id)
    )
    version = await db.get_one(TrainingVersion, version_id)
    training = await db.get_one(Training, version.training_id)
    assert profile is not None
    assignment = make_training_assignment(profile, training, version)
    db.add(assignment)
    await db.commit()
    return assignment


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
    replacement = await auth_client.post(
        f"{versions_url}/{hidden_draft.json()['id']}/publish",
        headers=mutation_headers(csrf, key="employee-training-replacement-publish"),
        json={"expected_revision": hidden_lesson.json()["revision"]},
    )
    assert replacement.status_code == 200

    user_id = await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        preferred_locale="en",
    )
    await attach_training_assignment(
        db_session,
        user_id=user_id,
        version_id=published_id,
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
    assert listing.json()["training"]["version_number"] == 1
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

    auth_client.cookies.clear()
    await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    unassigned = await auth_client.get("/api/v1/me/training")
    assert unassigned.status_code == 200
    assert unassigned.json()["assignment"] is None
    assert unassigned.json()["training"] is None
    assert unassigned.json()["modules"] == []
    assert unassigned.json()["progress"] is None
    assert unassigned.json()["next_action"] == "none"


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
        "assignment": None,
        "training": None,
        "modules": [],
        "progress": None,
        "next_action": "none",
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

    user_id = await attach_employee(
        auth_client,
        db_session,
        organization_id=organization_id,
        location_id=location_id,
    )
    await attach_training_assignment(
        db_session,
        user_id=user_id,
        version_id=version_id,
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
    home_schema = paths["/api/v1/me/training"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert home_schema["$ref"].endswith("/EmployeeTrainingHomeResponse")
    employee_schemas = {
        key: value
        for key, value in document["components"]["schemas"].items()
        if key.startswith("EmployeeTraining")
    }
    serialized = str(employee_schemas)
    for forbidden in ("revision", "object_key", "sha256", "base_version_id"):
        assert forbidden not in serialized
