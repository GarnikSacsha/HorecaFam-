import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import Settings
from app.db.base import Base
from app.db.safety import assert_safe_test_database
from app.db.session import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def database_settings() -> Settings:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured for dedicated PostgreSQL 16")
    settings = Settings(app_env="test", database_url=database_url)
    assert_safe_test_database(settings)
    return settings


@pytest.mark.integration
@pytest.mark.migration
def test_empty_database_reaches_alembic_head() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")

    command.current(config, check_heads=True)
    command.check(config)


def test_application_runtime_does_not_use_create_all() -> None:
    application_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (BACKEND_ROOT / "app").rglob("*.py")
    )

    assert "create_all" not in application_source


def test_identity_metadata_contains_only_stage_1_tables() -> None:
    assert set(Base.metadata.tables) == {
        "audit_events",
        "employee_profiles",
        "locations",
        "operational_roles",
        "organization_memberships",
        "organizations",
        "users",
    }


@pytest.mark.integration
@pytest.mark.migration
async def test_database_contains_stage_1_tables(
    migrated_test_database: Settings,
) -> None:
    engine = create_engine(migrated_test_database)
    try:
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
    finally:
        await engine.dispose()

    assert set(Base.metadata.tables) <= table_names
