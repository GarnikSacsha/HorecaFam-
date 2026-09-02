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


def test_railway_postgresql_url_is_normalized_for_asyncpg() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql://user:password@postgres.railway.internal:5432/railway",
    )

    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_log_level_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError, match="log_level"):
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
            log_level="TRACE",
        )


def test_auth_security_settings_fail_closed_without_keys() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
    )

    with pytest.raises(ValueError, match="MFA_ENCRYPTION_KEYS"):
        settings.validate_auth_security()


def test_auth_security_settings_reject_insecure_test_cookie() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        mfa_encryption_keys=["obvious-test-placeholder"],
        auth_throttle_hmac_key="x" * 32,
        session_cookie_secure=False,
    )

    with pytest.raises(ValueError, match="Secure Session cookies"):
        settings.validate_auth_security()


def test_invitation_security_settings_require_ordered_hmac_keys() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
    )

    with pytest.raises(ValueError, match="INVITATION_TOKEN_HMAC_KEYS"):
        settings.validate_invitation_security()


def test_invitation_security_settings_reject_short_hmac_key() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        invitation_token_hmac_keys=["short"],
    )

    with pytest.raises(ValueError, match="32 characters"):
        settings.validate_invitation_security()


def test_password_reset_security_requires_ordered_hmac_keys() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
    )

    with pytest.raises(ValueError, match="PASSWORD_RESET_TOKEN_HMAC_KEYS"):
        settings.validate_password_reset_security()


def test_password_reset_security_rejects_short_hmac_key() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        password_reset_token_hmac_keys=["short"],
    )

    with pytest.raises(ValueError, match="32 characters"):
        settings.validate_password_reset_security()


def test_worker_readiness_requires_complete_provider_configuration() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca",
        invitation_token_hmac_keys=["i" * 32],
        password_reset_token_hmac_keys=["r" * 32],
    )

    with pytest.raises(ValueError, match="PUBLIC_APP_URL"):
        settings.validate_worker_readiness()


def test_worker_readiness_rejects_insecure_public_url_outside_development() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca",
        invitation_token_hmac_keys=["i" * 32],
        password_reset_token_hmac_keys=["r" * 32],
        public_app_url="http://academy.example.com",
        resend_api_key="provider-secret",
        email_from_address="Bacara Academy <academy@example.com>",
    )

    with pytest.raises(ValueError, match="HTTPS"):
        settings.validate_worker_readiness()


def test_worker_readiness_accepts_complete_production_configuration() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca",
        invitation_token_hmac_keys=["i" * 32],
        password_reset_token_hmac_keys=["r" * 32],
        public_app_url="https://academy.example.com/",
        resend_api_key="provider-secret",
        email_from_address="Bacara Academy <academy@example.com>",
        worker_idle_seconds=0.25,
        worker_heartbeat_interval_seconds=5,
    )

    settings.validate_worker_readiness()
    assert settings.public_app_url == "https://academy.example.com"


def test_worker_idle_timing_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="worker_idle_seconds"):
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
            worker_idle_seconds=0,
        )


def test_worker_heartbeat_timing_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="worker_heartbeat_interval_seconds"):
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
            worker_heartbeat_interval_seconds=-1,
        )


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
