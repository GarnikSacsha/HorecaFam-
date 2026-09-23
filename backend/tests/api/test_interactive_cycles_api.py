from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.tokens import hash_secret
from tests.factories.interactive_training import arrange_interactive_runtime
from tests.integration.test_interactive_cycle_service import finish


async def test_cycle_restart_requires_csrf_and_owned_scope(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    runtime = await arrange_interactive_runtime(db_session)
    token, csrf = f"cycle-{uuid4()}", f"csrf-{uuid4()}"
    runtime.session.token_hash = hash_secret(token)
    runtime.session.csrf_token_hash = hash_secret(csrf)
    await db_session.commit()
    auth_client.cookies.set("horeca_session", token, path="/api/v1")
    lesson_id = runtime.persistence.lesson_version.lesson_id
    base = f"/api/v1/me/training/lessons/{lesson_id}/interactive-training"
    initial = await auth_client.get(base)
    assert initial.status_code == 200
    cycle = initial.json()["cycle"]
    assert cycle["status"] == "in_progress"
    payload = {"expected_cycle_id": cycle["id"]}
    no_csrf = await auth_client.post(
        base + "/cycles/restart", json=payload, headers={"Idempotency-Key": "restart"}
    )
    assert no_csrf.status_code == 403
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "restart"}
    active = await auth_client.post(base + "/cycles/restart", json=payload, headers=headers)
    assert active.status_code == 409
    await finish(db_session, runtime)
    for _ in range(2):
        response = await auth_client.post(base + "/cycles/restart", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["number"] == 2
        assert response.json()["remaining_count"] == 5
    foreign = await auth_client.post(
        base + "/cycles/restart",
        json={"expected_cycle_id": str(uuid4())},
        headers={**headers, "Idempotency-Key": "foreign"},
    )
    assert foreign.status_code == 404
    text = response.text
    for secret in ("grading_payload", "correct_option_ids", "explanation_payload"):
        assert secret not in text
