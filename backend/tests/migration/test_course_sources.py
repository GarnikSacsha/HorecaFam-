import asyncio
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
    make_attempt_result,
)
from tests.integration.test_assessment_persistence import _make_context
from tests.integration.test_standard_sources import _source
from tests.migration.test_migrations import (
    BACKEND_ROOT,
    _seed_attention_backfill_history,
    _source_history_snapshot,
    _truncate_backfill_fixture_data,
    database_settings,
)


async def _seed_extension(settings: Settings, kind: str) -> None:
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as db:
            if kind == "standards":
                await _source(db)
            else:
                context = await _make_context(db)
                assessment = make_assessment(
                    context.training,
                    context.lesson_version,
                    assessment_type="course_knowledge_check",
                )
                db.add(assessment)
                await db.flush()
                version = make_assessment_version(
                    assessment,
                    context.training_version,
                    context.lesson_version,
                    question_count=20,
                    threshold_percent=None,
                    feedback_policy="after_final_submission",
                )
                db.add(version)
                await db.flush()
                attempt = make_assessment_attempt(
                    context.employee,
                    context.assignment,
                    version,
                    question_count=20,
                    status="completed",
                    completed_at=datetime.now(UTC),
                )
                db.add(attempt)
                await db.flush()
                db.add(
                    make_attempt_result(
                        attempt,
                        total_count=20,
                        correct_count=20,
                        score_basis_points=10000,
                        pass_status=None,
                    )
                )
            await db.commit()
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "kind,target,message",
    [
        ("standards", "0023_course_assessment_type", "discard standard sources"),
        ("course", "0022_module_position_audiences", "discard course knowledge checks"),
    ],
)
def test_extension_downgrade_refuses_data_loss(kind: str, target: str, message: str) -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    asyncio.run(_truncate_backfill_fixture_data(settings))
    try:
        asyncio.run(_seed_extension(settings, kind))
        with pytest.raises(RuntimeError, match=message):
            command.downgrade(config, target)
        command.current(config, check_heads=True)
    finally:
        asyncio.run(_truncate_backfill_fixture_data(settings))
        command.upgrade(config, "head")


async def _assert_type_backfill(settings: Settings) -> None:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT s.assessment_type, v.assessment_type, "
                    "a.assessment_type, r.assessment_type "
                    "FROM attempt_results r JOIN assessment_attempts a ON a.id=r.attempt_id "
                    "JOIN assessment_versions v ON v.id=a.assessment_version_id "
                    "JOIN assessments s ON s.id=v.assessment_id"
                )
            )
            values = list(rows)
            assert values
            assert all(len(set(row)) == 1 for row in values)
            assert {row[0] for row in values} == {"whole_menu_knowledge_check", "menu_final_exam"}
    finally:
        await engine.dispose()


def test_type_backfill_preserves_menu_attempts_and_results() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    asyncio.run(_truncate_backfill_fixture_data(settings))
    try:
        asyncio.run(_seed_attention_backfill_history(settings))
        before = asyncio.run(_source_history_snapshot(settings))
        command.downgrade(config, "0022_module_position_audiences")
        command.upgrade(config, "head")
        asyncio.run(_assert_type_backfill(settings))
        assert asyncio.run(_source_history_snapshot(settings)) == before
    finally:
        asyncio.run(_truncate_backfill_fixture_data(settings))
        command.upgrade(config, "head")
