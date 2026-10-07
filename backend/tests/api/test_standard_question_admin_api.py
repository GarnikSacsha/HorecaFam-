from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.test_menu_admin_api import arrange_admin


async def test_standard_generation_admin_boundary_requires_authentication_and_csrf(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    path = (
        f"/api/v1/organizations/{uuid4()}/locations/{uuid4()}/training-versions/{uuid4()}"
        "/standard-question-candidates/generate"
    )
    response = await auth_client.post(path, headers={"Idempotency-Key": "standards-anonymous"})
    assert response.status_code == 401
    organization_id, location_id, _admin_id, _csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    path = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}"
        f"/training-versions/{uuid4()}/standard-question-candidates/generate"
    )
    response = await auth_client.post(path, headers={"Idempotency-Key": "standards-no-csrf"})
    assert response.status_code == 403
