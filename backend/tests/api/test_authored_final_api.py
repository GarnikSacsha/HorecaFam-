from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.test_menu_admin_api import arrange_admin, mutation_headers


@pytest.mark.parametrize("kind", ["authored", "version"])
async def test_new_admin_mutations_enforce_scope_csrf_and_idempotency(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    kind: str,
) -> None:
    org, location, _, csrf = await arrange_admin(auth_client, auth_app, db_session)
    if kind == "authored":
        suffix = "question-candidates/authored"
        payload = {
            "training_version_id": str(uuid4()),
            "lesson_version_id": str(uuid4()),
            "prompt_payload": {
                "stem": "Який гарнір?",
                "selection_mode": "single",
                "options": [{"stable_key": str(i), "text": str(i)} for i in range(4)],
            },
            "answer_payload": {"correct_option_keys": ["0"]},
            "explanation_payload": {
                "text": "Опис джерела",
                "authoring": {
                    "menu_version_id": str(uuid4()),
                    "menu_item_version_id": str(uuid4()),
                    "source_quote": "Рис",
                    "option_rationales": {str(i): "Підстава" for i in range(4)},
                },
            },
        }
    else:
        suffix = f"training-versions/{uuid4()}/final-exam/versions"
        payload = {
            "expected_assessment_version_id": str(uuid4()),
            "policy": {
                "question_version_ids": [str(uuid4()) for _ in range(20)],
                "buckets": [
                    {"key": key, "count": count, "category_ids": [str(uuid4())]}
                    for key, count in (("food", 10), ("drinks", 4), ("desserts", 3), ("other", 3))
                ],
            },
        }
    prefix = f"/api/v1/organizations/{org}/locations/{location}/"
    missing_csrf = await auth_client.post(
        prefix + suffix, json=payload, headers={"Idempotency-Key": "create"}
    )
    assert missing_csrf.status_code == 403
    headers = mutation_headers(csrf, key="create")
    missing_key = await auth_client.post(
        prefix + suffix,
        json=payload,
        headers={key: value for key, value in headers.items() if key.lower() != "idempotency-key"},
    )
    assert missing_key.status_code == 422
    unavailable = await auth_client.post(prefix + suffix, json=payload, headers=headers)
    assert unavailable.status_code == 404
    foreign = await auth_client.post(
        f"/api/v1/organizations/{uuid4()}/locations/{location}/" + suffix,
        json=payload,
        headers=headers,
    )
    assert foreign.status_code == 404
