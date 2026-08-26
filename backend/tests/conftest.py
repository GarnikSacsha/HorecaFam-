import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.db.safety import assert_safe_test_database
from app.db.session import create_engine, create_session_factory

BACKEND_ROOT = Path(__file__).resolve().parents[1]
IDENTITY_TABLES = (
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
