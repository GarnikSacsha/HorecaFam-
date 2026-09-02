from pathlib import Path

import pytest

from app.core.config import Settings
from app.main import create_app


async def test_application_disposes_database_engine_on_shutdown() -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        )
    )
    disposed = False

    class RecordingEngine:
        async def dispose(self) -> None:
            nonlocal disposed
            disposed = True

    app.state.engine = RecordingEngine()
    async with app.router.lifespan_context(app):
        pass

    assert disposed


def test_api_server_uses_platform_port(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import api_server

    captured: dict[str, object] = {}

    def record_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setattr(api_server.uvicorn, "run", record_run)

    api_server.main()

    assert captured == {
        "app": "app.main:create_app",
        "factory": True,
        "host": "0.0.0.0",
        "port": 9123,
    }


def test_backend_container_is_unprivileged_and_uses_api_entrypoint() -> None:
    dockerfile = Path(__file__).parents[2] / "Dockerfile"
    contents = dockerfile.read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in contents
    assert "USER horeca" in contents
    assert 'CMD ["python", "-m", "app.api_server"]' in contents
