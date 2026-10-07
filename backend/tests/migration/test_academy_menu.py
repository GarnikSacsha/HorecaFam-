import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.models import AcademyArticle
from tests.factories.identity import make_location, make_organization
from tests.migration.test_migrations import (
    BACKEND_ROOT,
    _seed_attention_backfill_history,
    _truncate_backfill_fixture_data,
    database_settings,
)


async def seed(settings: Settings, kind: str) -> None:
    if kind == "preparation":
        await _seed_attention_backfill_history(settings)
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as db:
            if kind == "preparation":
                await db.execute(
                    text(
                        "UPDATE menu_item_versions SET preparation = '{\"volume_ml\": 250}'::jsonb"
                    )
                )
            else:
                org = make_organization()
                loc = make_location(org)
                db.add_all([org, loc])
                await db.flush()
                db.add(
                    AcademyArticle(
                        organization_id=org.id,
                        location_id=loc.id,
                        slug="preserve",
                        title_uk="Стаття",
                        summary_uk="Опис",
                        body_uk="Текст",
                        category="service",
                        all_positions=True,
                    )
                )
            await db.commit()
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "kind,target,message",
    [
        ("academy", "0025_menu_preparation", "discard Academy articles"),
        ("preparation", "0024_standard_sources", "discard menu preparation details"),
    ],
)
def test_new_content_blocks_destructive_downgrade(kind: str, target: str, message: str) -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    asyncio.run(_truncate_backfill_fixture_data(settings))
    try:
        asyncio.run(seed(settings, kind))
        with pytest.raises(RuntimeError, match=message):
            command.downgrade(config, target)
        command.current(config, check_heads=True)
    finally:
        asyncio.run(_truncate_backfill_fixture_data(settings))
        command.upgrade(config, "head")
