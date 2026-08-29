from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import assessments as assessment_routes
from app.services.question_generation import CandidateGenerationResult
from tests.api.test_menu_admin_api import arrange_admin, mutation_headers


async def test_candidate_generation_requires_admin_csrf_and_idempotency(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )

    async def fake_generate(*_args: object, **_kwargs: object) -> CandidateGenerationResult:
        return CandidateGenerationResult(
            created_count=2,
            existing_count=0,
            stale_candidate_count=0,
            stale_question_count=0,
        )

    monkeypatch.setattr(assessment_routes, "generate_question_candidates", fake_generate)
    url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        "question-candidates/generate"
    )
    payload = {
        "menu_version_id": str(uuid4()),
        "training_version_id": str(uuid4()),
    }

    missing_csrf = await auth_client.post(
        url,
        headers={"Idempotency-Key": "candidate-generation"},
        json=payload,
    )
    assert missing_csrf.status_code == 403

    generated = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="candidate-generation"),
        json=payload,
    )
    assert generated.status_code == 200
    assert generated.json() == {
        "created_count": 2,
        "existing_count": 0,
        "stale_candidate_count": 0,
        "stale_question_count": 0,
        "replayed": False,
    }

    replay = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="candidate-generation"),
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True

    conflict = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="candidate-generation"),
        json={**payload, "menu_version_id": str(uuid4())},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_assessment_admin_routes_are_present_and_foreign_scope_is_hidden(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, _csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    foreign = await auth_client.get(
        f"/api/v1/organizations/{uuid4()}/locations/{location_id}/question-candidates"
    )
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "RESOURCE_NOT_FOUND"

    openapi = auth_app.openapi()
    expected_paths = {
        f"/api/v1/organizations/{{organization_id}}/locations/{{location_id}}/{suffix}"
        for suffix in (
            "question-candidates/generate",
            "question-candidates",
            "question-candidates/batch-approve",
            "question-candidates/{candidate_id}",
            "question-candidates/{candidate_id}/approve",
            "question-candidates/{candidate_id}/reject",
            "training-versions/{version_id}/interactive-training/readiness",
        )
    }
    assert expected_paths <= set(openapi["paths"])
    assert {
        "/api/v1/me/training/lessons/{lesson_id}/interactive-training/attempts",
        "/api/v1/me/training/interactive-training/attempts/{attempt_id}",
        "/api/v1/me/training/interactive-training/attempts/{attempt_id}/takeover",
    } <= set(openapi["paths"])
    safe_question_properties = openapi["components"]["schemas"][
        "InteractiveAttemptQuestionResponse"
    ]["properties"]
    assert "grading_payload" not in safe_question_properties
    assert "explanation_payload" not in safe_question_properties
    safe_option_properties = openapi["components"]["schemas"]["InteractiveAttemptOptionResponse"][
        "properties"
    ]
    assert "is_correct" not in safe_option_properties
