import asyncio
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

ASSIGNMENT_ROLLOUT_TABLES = {
    "lesson_completions",
    "rollout_employee_impacts",
    "rollout_lesson_rules",
    "training_assignments",
    "training_rollouts",
    "training_version_audiences",
}

INTERACTIVE_TRAINING_TABLES = {
    "assessment_attempts",
    "assessment_question_pools",
    "assessment_readiness",
    "assessment_version_translations",
    "assessment_versions",
    "assessments",
    "attempt_device_leases",
    "attempt_options",
    "attempt_questions",
    "attempt_results",
    "question_candidates",
    "question_generation_rules",
    "question_option_translations",
    "question_options",
    "question_source_links",
    "question_version_translations",
    "question_versions",
    "questions",
    "submitted_answers",
}


def database_settings() -> Settings:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured for dedicated PostgreSQL 16")
    settings = Settings(app_env="test", database_url=database_url)
    assert_safe_test_database(settings)
    return settings


async def database_table_names(settings: Settings) -> set[str]:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
    finally:
        await engine.dispose()


async def database_column_names(settings: Settings, table_name: str) -> set[str]:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: {
                    column["name"] for column in inspect(sync_connection).get_columns(table_name)
                }
            )
    finally:
        await engine.dispose()


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


@pytest.mark.integration
@pytest.mark.migration
def test_invitation_outbox_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0004_invitation_lifecycle")
        table_names = asyncio.run(database_table_names(settings))

        assert "invitations" in table_names
        assert "background_jobs" not in table_names
        assert "email_deliveries" not in table_names
    finally:
        command.upgrade(config, "head")


def test_metadata_contains_current_backend_tables() -> None:
    assert set(Base.metadata.tables) == {
        "admin_access",
        "allergens",
        "api_idempotency_records",
        "assessment_attempts",
        "assessment_question_pools",
        "assessment_readiness",
        "assessment_version_translations",
        "assessment_versions",
        "assessments",
        "audit_events",
        "auth_rate_limit_buckets",
        "attempt_device_leases",
        "attempt_options",
        "attempt_questions",
        "attempt_results",
        "background_jobs",
        "email_deliveries",
        "employee_profiles",
        "invitation_rate_limit_buckets",
        "invitations",
        "locations",
        "menu_categories",
        "menu_component_version_translations",
        "menu_component_versions",
        "menu_components",
        "menu_item_version_allergens",
        "menu_item_version_components",
        "menu_item_version_translations",
        "menu_item_versions",
        "menu_import_findings",
        "menu_imports",
        "menu_items",
        "menu_sections",
        "menu_version_category_translations",
        "menu_version_categories",
        "menu_version_item_deltas",
        "menu_version_section_translations",
        "menu_version_sections",
        "menu_versions",
        "menus",
        "mfa_challenges",
        "mfa_credentials",
        "operational_roles",
        "organization_memberships",
        "organizations",
        "question_candidates",
        "question_generation_rules",
        "question_option_translations",
        "question_options",
        "question_source_links",
        "question_version_translations",
        "question_versions",
        "questions",
        "sessions",
        "submitted_answers",
        "assets",
        "lesson_content_block_translations",
        "lesson_content_blocks",
        "lesson_translations",
        "lesson_versions",
        "lessons",
        "training_module_translations",
        "training_module_versions",
        "training_modules",
        "training_version_menu_dependencies",
        "training_version_audiences",
        "training_assignments",
        "lesson_completions",
        "training_rollouts",
        "rollout_lesson_rules",
        "rollout_employee_impacts",
        "training_versions",
        "trainings",
        "users",
    }


@pytest.mark.integration
@pytest.mark.migration
def test_menu_source_of_truth_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0005_invitation_email_outbox")
        table_names = asyncio.run(database_table_names(settings))

        assert "menus" not in table_names
        assert "menu_versions" not in table_names
        assert "menu_item_versions" not in table_names
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_menu_import_review_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0006_menu_source_of_truth")
        table_names = asyncio.run(database_table_names(settings))

        assert "menu_imports" not in table_names
        assert "menu_import_findings" not in table_names
        assert "menus" in table_names
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_training_content_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0007_menu_import_review")
        table_names = asyncio.run(database_table_names(settings))

        assert "trainings" not in table_names
        assert "training_versions" not in table_names
        assert "lesson_content_blocks" not in table_names
        assert "assets" not in table_names
        assert "menus" in table_names
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_assignment_completion_rollout_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        current_tables = asyncio.run(database_table_names(settings))
        assert current_tables >= ASSIGNMENT_ROLLOUT_TABLES
        current_membership_columns = asyncio.run(
            database_column_names(settings, "organization_memberships")
        )
        assert "training_participation_status" in current_membership_columns

        command.downgrade(config, "0008_training_content")
        downgraded_tables = asyncio.run(database_table_names(settings))

        assert ASSIGNMENT_ROLLOUT_TABLES.isdisjoint(downgraded_tables)
        assert "training_versions" in downgraded_tables
        assert "lesson_versions" in downgraded_tables
        downgraded_membership_columns = asyncio.run(
            database_column_names(settings, "organization_memberships")
        )
        assert "training_participation_status" not in downgraded_membership_columns
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_interactive_training_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        current_tables = asyncio.run(database_table_names(settings))
        assert current_tables >= INTERACTIVE_TRAINING_TABLES

        command.downgrade(config, "0009_assignment_completion_rollout")
        downgraded_tables = asyncio.run(database_table_names(settings))

        assert INTERACTIVE_TRAINING_TABLES.isdisjoint(downgraded_tables)
        assert "training_assignments" in downgraded_tables
        assert "lesson_completions" in downgraded_tables
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
async def test_database_contains_current_tables(
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
