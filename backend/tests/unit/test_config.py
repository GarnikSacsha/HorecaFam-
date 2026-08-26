import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.db.safety import UnsafeTestDatabaseError, assert_safe_test_database


def test_missing_required_configuration_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = {str(error["loc"][0]) for error in exc_info.value.errors()}
    assert errors == {"app_env", "database_url"}


def test_database_url_must_use_async_postgresql() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings(app_env="test", database_url="sqlite+aiosqlite:///horeca_test.db")


def test_test_database_guard_accepts_explicit_test_database() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test_gw0",
    )

    assert_safe_test_database(settings)


@pytest.mark.parametrize("app_env", ["development", "staging", "production"])
def test_test_database_guard_rejects_non_test_environment(app_env: str) -> None:
    settings = Settings(
        app_env=app_env,
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
    )

    with pytest.raises(UnsafeTestDatabaseError, match="APP_ENV=test"):
        assert_safe_test_database(settings)


@pytest.mark.parametrize(
    "database_name", ["horeca", "horeca_dev", "horeca_staging", "horeca_production", "postgres"]
)
def test_test_database_guard_rejects_non_test_database(database_name: str) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"postgresql+asyncpg://postgres:postgres@localhost:5432/{database_name}",
    )

    with pytest.raises(UnsafeTestDatabaseError, match="test-scoped"):
        assert_safe_test_database(settings)
