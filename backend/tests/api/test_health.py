from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


async def test_application_can_be_instantiated_in_test_mode() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
    )

    app = create_app(settings)

    assert app.state.settings is settings


async def test_health_returns_approved_contract() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
