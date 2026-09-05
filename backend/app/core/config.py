from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnvironment
    database_url: str
    log_level: LogLevel = "INFO"
    mfa_encryption_keys: list[SecretStr] = []
    auth_throttle_hmac_key: SecretStr | None = None
    invitation_token_hmac_keys: list[SecretStr] = []
    password_reset_token_hmac_keys: list[SecretStr] = []
    public_app_url: str | None = None
    resend_api_key: SecretStr | None = None
    email_from_address: str | None = None
    worker_id: str = "horeca-worker"
    worker_idle_seconds: float = 1.0
    worker_heartbeat_interval_seconds: float = 15.0
    storage_bucket: str | None = None
    storage_endpoint_url: str | None = None
    storage_region: str = "auto"
    storage_addressing_style: Literal["auto", "virtual", "path"] = "auto"
    storage_access_key_id: SecretStr | None = None
    storage_secret_access_key: SecretStr | None = None
    cors_allowed_origins: list[str] = []
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_name: str = "horeca_session"
    mfa_challenge_cookie_name: str = "horeca_mfa_challenge"

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value

    @field_validator("public_app_url")
    @classmethod
    def normalize_public_app_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("PUBLIC_APP_URL must be an absolute HTTP(S) URL")
        return normalized

    @field_validator("worker_idle_seconds", "worker_heartbeat_interval_seconds")
    @classmethod
    def require_positive_worker_timing(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Worker timing must be positive")
        return value

    def validate_auth_security(self) -> None:
        if not self.mfa_encryption_keys:
            raise ValueError("MFA_ENCRYPTION_KEYS must contain at least one key")
        if self.auth_throttle_hmac_key is None:
            raise ValueError("AUTH_THROTTLE_HMAC_KEY is required")
        if len(self.auth_throttle_hmac_key.get_secret_value()) < 32:
            raise ValueError("AUTH_THROTTLE_HMAC_KEY must contain at least 32 characters")
        if "*" in self.cors_allowed_origins:
            raise ValueError("Credentialed CORS cannot allow every origin")
        if self.app_env in {"test", "staging", "production"} and not self.session_cookie_secure:
            raise ValueError("Secure Session cookies are required outside development")

    def validate_invitation_security(self) -> None:
        if not self.invitation_token_hmac_keys:
            raise ValueError("INVITATION_TOKEN_HMAC_KEYS must contain at least one key")
        if any(len(key.get_secret_value()) < 32 for key in self.invitation_token_hmac_keys):
            raise ValueError("Every INVITATION_TOKEN_HMAC_KEYS entry must contain 32 characters")

    def validate_password_reset_security(self) -> None:
        if not self.password_reset_token_hmac_keys:
            raise ValueError("PASSWORD_RESET_TOKEN_HMAC_KEYS must contain at least one key")
        if any(len(key.get_secret_value()) < 32 for key in self.password_reset_token_hmac_keys):
            raise ValueError(
                "Every PASSWORD_RESET_TOKEN_HMAC_KEYS entry must contain 32 characters"
            )

    def validate_private_storage(self) -> None:
        required = (
            self.storage_bucket,
            self.storage_endpoint_url,
            self.storage_access_key_id,
            self.storage_secret_access_key,
        )
        if any(value is None for value in required):
            raise ValueError("Private storage configuration is incomplete")

    def validate_worker_readiness(self) -> None:
        self.validate_invitation_security()
        self.validate_password_reset_security()
        if self.public_app_url is None:
            raise ValueError("PUBLIC_APP_URL is required for the worker")
        if self.app_env in {"staging", "production"} and not self.public_app_url.startswith(
            "https://"
        ):
            raise ValueError("PUBLIC_APP_URL must use HTTPS outside development and test")
        if self.resend_api_key is None:
            raise ValueError("RESEND_API_KEY is required for the worker")
        if not self.email_from_address or not self.email_from_address.strip():
            raise ValueError("EMAIL_FROM_ADDRESS is required for the worker")


@lru_cache
def get_settings() -> Settings:
    return Settings()
