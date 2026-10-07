from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentVersion,
    LessonVersion,
    OperationalRole,
    QuestionCandidate,
    StandardRuleVersion,
    TrainingModuleAudience,
    TrainingModuleVersion,
    TrainingVersion,
)
from app.models.enums import ContentBlockType
from app.schemas.training import validate_content_payload
from app.services.training_catalog import COURSES
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu


async def test_content_pack_appends_draft_without_overwriting_menu(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    org, loc, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org}/locations/{loc}/training-versions"
    draft_response = await auth_client.post(
        base,
        headers=mutation_headers(csrf, key="pack-draft"),
        json={"base_version_id": None},
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()
    response = await auth_client.post(
        f"{base}/{draft['id']}/content-pack",
        headers=mutation_headers(csrf, key="pack-install"),
        json={"expected_revision": draft["revision"], "acknowledge_generic_content": True},
    )
    assert response.status_code == 200
    assert response.json()["module_count"] == 3
    assert response.json()["lesson_count"] == 23
    assert response.json()["question_count"] == 45
    replay = await auth_client.post(
        f"{base}/{draft['id']}/content-pack",
        headers=mutation_headers(csrf, key="pack-install"),
        json={"expected_revision": draft["revision"], "acknowledge_generic_content": True},
    )
    assert replay.status_code == 200 and replay.json()["replayed"]
    updated = (await auth_client.get(f"{base}/{draft['id']}")).json()
    assert updated["modules"][0] == draft["modules"][0]
    assert updated["status"] == "draft"
    assert len(updated["modules"]) == 4
    assert [len(module["lessons"]) for module in updated["modules"][1:]] == [6, 6, 11]
    for module in updated["modules"][1:]:
        for lesson in module["lessons"]:
            for block in lesson["content_blocks"]:
                validate_content_payload(ContentBlockType(block["type"]), block["payload"])
    assert await db_session.scalar(select(func.count(StandardRuleVersion.id))) == 45
    assert await db_session.scalar(select(func.count(AssessmentVersion.id))) == 0
    assert await db_session.scalar(select(func.count(QuestionCandidate.id))) == 0
    assert [len(course.scenarios) for course in COURSES] == [15, 20, 10]
    again = await auth_client.post(
        f"{base}/{draft['id']}/content-pack",
        headers=mutation_headers(csrf, key="another-click"),
        json={"expected_revision": updated["revision"], "acknowledge_generic_content": True},
    )
    assert again.status_code == 200 and again.json()["replayed"]
    assert await db_session.scalar(select(func.count(LessonVersion.id))) == 23
    audiences = list(await db_session.scalars(select(TrainingModuleAudience)))
    assert len(audiences) == 5
    runner_ids = {
        row.operational_role_id
        for row in audiences
        if str(row.training_module_version_id) == updated["modules"][1]["id"]
    }
    bartender_ids = {
        row.operational_role_id
        for row in audiences
        if str(row.training_module_version_id) == updated["modules"][2]["id"]
    }
    assert not runner_ids & bartender_ids


async def test_content_pack_requires_review_scope_revision_and_csrf(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    org, loc, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    base = f"/api/v1/organizations/{org}/locations/{loc}/training-versions"
    draft = (
        await auth_client.post(base, headers=mutation_headers(csrf, key="draft"), json={})
    ).json()
    url = f"{base}/{draft['id']}/content-pack"
    payload = {"expected_revision": draft["revision"], "acknowledge_generic_content": True}
    assert (
        await auth_client.post(url, headers={"Idempotency-Key": "bad"}, json=payload)
    ).status_code == 403
    for change, code in (
        ({"acknowledge_generic_content": False}, 422),
        ({"expected_revision": 99}, 409),
        ({"waiter_role_id": str(uuid4())}, 409),
    ):
        response = await auth_client.post(
            url, headers=mutation_headers(csrf, key=str(uuid4())), json={**payload, **change}
        )
        assert response.status_code == code
    assert await db_session.scalar(select(func.count(TrainingModuleVersion.id))) == 1
    assert await db_session.scalar(select(func.count(StandardRuleVersion.id))) == 0
    runner = OperationalRole(organization_id=org, code="runner", name_uk="Runner", status="active")
    db_session.add(runner)
    await db_session.commit()
    wrong_mapping = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="same-position"),
        json={**payload, "waiter_role_id": str(runner.id)},
    )
    assert wrong_mapping.status_code == 409
    assert wrong_mapping.json()["code"] == "POSITION_MAPPING_CONFLICT"
    assert (
        await db_session.scalar(
            select(OperationalRole.id).where(OperationalRole.code == "bartender")
        )
        is None
    )
    foreign = url.replace(str(loc), str(uuid4()))
    assert (
        await auth_client.post(foreign, headers=mutation_headers(csrf, key="foreign"), json=payload)
    ).status_code == 404
    preview = await auth_client.get(f"/api/v1/organizations/{org}/training-content-pack")
    assert preview.status_code == 200 and len(preview.json()["courses"]) == 3
    auth_client.cookies.clear()
    assert (
        await auth_client.get(f"/api/v1/organizations/{org}/training-content-pack")
    ).status_code == 401


async def test_content_pack_can_publish_then_generate_review_candidates(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    org, loc, _admin, csrf = await arrange_admin(auth_client, auth_app, db_session)
    await publish_menu(
        auth_client, organization_id=org, location_id=loc, csrf=csrf, key_prefix="pack-menu"
    )
    draft = await arrange_ready_training(
        auth_client, organization_id=org, location_id=loc, csrf=csrf, key_prefix="pack-training"
    )
    base = f"/api/v1/organizations/{org}/locations/{loc}/training-versions/{draft['id']}"
    installed = await auth_client.post(
        base + "/content-pack",
        headers=mutation_headers(csrf, key="pack"),
        json={"expected_revision": draft["revision"], "acknowledge_generic_content": True},
    )
    assert installed.status_code == 200
    readiness = (await auth_client.get(base + "/readiness")).json()
    assert readiness["can_publish"], readiness["blocking_errors"]
    publication = await auth_client.post(
        base + "/publish",
        headers=mutation_headers(csrf, key="publish"),
        json={"expected_revision": installed.json()["revision"]},
    )
    assert publication.status_code == 200
    generated = await auth_client.post(
        base + "/standard-question-candidates/generate",
        headers=mutation_headers(csrf, key="generate"),
    )
    assert generated.status_code == 200
    assert generated.json()["created_count"] == 45
    assert set(await db_session.scalars(select(QuestionCandidate.status))) == {"needs_review"}
    assert await db_session.scalar(select(func.count(AssessmentVersion.id))) == 0
    version = await db_session.get_one(TrainingVersion, UUID(str(draft["id"])))
    rejected = await auth_client.post(
        base + "/content-pack",
        headers=mutation_headers(csrf, key="published-pack"),
        json={"expected_revision": version.revision, "acknowledge_generic_content": True},
    )
    assert rejected.status_code == 409
