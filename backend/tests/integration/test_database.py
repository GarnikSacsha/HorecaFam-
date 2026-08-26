import os

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.db.safety import assert_safe_test_database
from app.db.session import create_engine, create_session_factory


def database_settings() -> Settings:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured for dedicated PostgreSQL 16")
    settings = Settings(app_env="test", database_url=database_url)
    assert_safe_test_database(settings)
    return settings


@pytest.mark.integration
async def test_async_session_executes_real_postgresql_round_trip() -> None:
    settings = database_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            assert await session.scalar(text("SELECT 1")) == 1
            server_version = await session.scalar(text("SHOW server_version_num"))
        assert engine.dialect.name == "postgresql"
        assert int(str(server_version)) // 10_000 == 16
    finally:
        await engine.dispose()
