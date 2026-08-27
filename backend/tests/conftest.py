import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.db.safety import assert_safe_test_database
from app.db.session import create_engine, create_session_factory
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
IDENTITY_TABLES = (
    "menu_version_item_deltas",
    "menu_item_version_allergens",
    "menu_item_version_components",
    "menu_component_version_translations",
    "menu_item_version_translations",
    "menu_version_category_translations",
    "menu_version_section_translations",
    "menu_item_versions",
    "menu_component_versions",
    "menu_version_categories",
    "menu_version_sections",
    "menu_versions",
    "allergens",
    "menu_components",
    "menu_items",
    "menu_categories",
    "menu_sections",
    "menus",
    "email_deliveries",
    "background_jobs",
    "invitation_rate_limit_buckets",
    "api_idempotency_records",
    "invitations",
    "auth_rate_limit_buckets",
    "mfa_challenges",
    "mfa_credentials",
    "sessions",
    "admin_access",
    "audit_events",
    "employee_profiles",
    "organization_memberships",
    "operational_roles",
    "locations",
    "users",
    "organizations",
)


@pytest.fixture(scope="session")
def test_database_settings() -> Settings:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured for dedicated PostgreSQL 16")
    if os.getenv("APP_ENV") != "test":
        pytest.fail("PostgreSQL tests require APP_ENV=test")

    settings = Settings(app_env="test", database_url=database_url)
    assert_safe_test_database(settings)
    return settings


@pytest.fixture(scope="session")
def migrated_test_database(test_database_settings: Settings) -> Settings:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", test_database_settings.database_url)
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    # Alembic fileConfig вимикає вже створені логери в процесі pytest.
    logging.getLogger("app.errors").disabled = False
    return test_database_settings


async def _truncate_identity_tables(engine: AsyncEngine) -> None:
    table_list = ", ".join(IDENTITY_TABLES)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))


@pytest_asyncio.fixture
async def db_session(migrated_test_database: Settings) -> AsyncIterator[AsyncSession]:
    engine = create_engine(migrated_test_database)
    try:
        await _truncate_identity_tables(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            yield session
            await session.rollback()
        await _truncate_identity_tables(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def auth_settings(migrated_test_database: Settings) -> Settings:
    return Settings(
        app_env="test",
        database_url=migrated_test_database.database_url,
        mfa_encryption_keys=[Fernet.generate_key().decode("ascii")],
        auth_throttle_hmac_key="test-only-auth-throttle-key-value",
        invitation_token_hmac_keys=["test-only-invitation-token-key-value"],
        cors_allowed_origins=["https://frontend.test"],
        session_cookie_secure=True,
    )


@pytest_asyncio.fixture
async def auth_app(auth_settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(auth_settings)
    yield application
    await application.state.engine.dispose()


@pytest_asyncio.fixture
async def auth_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="https://api.test",
    ) as client:
        yield client
