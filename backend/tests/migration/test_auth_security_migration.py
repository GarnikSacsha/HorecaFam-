import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db.session import create_engine
from tests.migration.test_migrations import BACKEND_ROOT, database_settings


@pytest.mark.integration
@pytest.mark.migration
def test_auth_budget_constraint_round_trip() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    async def constraint() -> str:
        engine = create_engine(settings)
        try:
            async with engine.connect() as connection:
                constraints = await connection.run_sync(
                    lambda conn: inspect(conn).get_check_constraints("auth_rate_limit_buckets")
                )
                return str(
                    next(
                        row["sqltext"]
                        for row in constraints
                        if row["name"] == "ck_auth_rate_limit_buckets_action_allowed"
                    )
                )
        finally:
            await engine.dispose()

    command.upgrade(config, "head")
    try:
        assert "reauth" in asyncio.run(constraint())
        command.downgrade(config, "0018_job_runtime")
        previous = asyncio.run(constraint())
        assert "reauth" not in previous and "mfa" not in previous
    finally:
        command.upgrade(config, "head")
    current = asyncio.run(constraint())
    assert "reauth" in current and "mfa" in current
    command.current(config, check_heads=True)
    command.check(config)
