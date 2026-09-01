import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.core.config import Settings
from app.db.base import Base
from app.db.safety import assert_safe_test_database
from app.db.session import create_engine, create_session_factory
from app.models import Organization
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
    make_attempt_question,
    make_attempt_result,
    make_submitted_answer,
)
from tests.factories.identity import make_employee_profile, make_membership, make_user
from tests.factories.menu import (
    make_allergen,
    make_item_allergen,
    make_item_version,
    make_menu,
    make_menu_category,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_version_category,
    make_version_section,
)
from tests.factories.training import make_training_assignment
from tests.integration.test_assessment_persistence import _make_context

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

PRACTICE_TABLES = {"assessment_eligibilities"}

ATTENTION_RETAKE_TABLES = {
    "attention_case_actions",
    "attention_case_sources",
    "attention_cases",
    "critical_errors",
    "retake_requirement_actions",
    "retake_requirements",
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


async def generation_rules(settings: Settings) -> set[tuple[str, int, str]]:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT code, version, mechanic "
                    "FROM question_generation_rules WHERE status = 'active'"
                )
            )
            return {(row.code, row.version, row.mechanic) for row in rows}
    finally:
        await engine.dispose()


async def _truncate_backfill_fixture_data(settings: Settings) -> None:
    engine = create_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE organizations, users, allergens, "
                    "question_generation_rules CASCADE"
                )
            )
    finally:
        await engine.dispose()


async def _seed_attention_backfill_history(settings: Settings) -> dict[str, object]:
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            context = await _make_context(session)
            now = datetime.now(UTC).replace(microsecond=0)

            menu = make_menu(context.training.organization_id, context.training.location_id)
            section = make_menu_section(menu)
            category = make_menu_category(menu)
            item = make_menu_item(menu)
            allergen = make_allergen()
            menu_version = make_menu_version(menu, context.actor.id)
            session.add_all([menu, section, category, item, allergen, menu_version])
            await session.flush()
            version_section = make_version_section(menu_version, section)
            session.add(version_section)
            await session.flush()
            version_category = make_version_category(menu_version, category, version_section)
            session.add(version_category)
            await session.flush()
            item_version = make_item_version(menu_version, item, version_category)
            session.add(item_version)
            await session.flush()
            item_allergen = make_item_allergen(menu_version, item_version, allergen)
            session.add(item_allergen)

            practice = make_assessment(
                context.training,
                None,
                assessment_type="whole_menu_knowledge_check",
            )
            final_exam = make_assessment(
                context.training,
                None,
                assessment_type="menu_final_exam",
            )
            session.add_all([practice, final_exam])
            await session.flush()
            practice_version = make_assessment_version(
                practice,
                context.training_version,
                None,
                question_count=10,
                threshold_percent=40,
                feedback_policy="after_final_submission",
            )
            final_exam_version = make_assessment_version(
                final_exam,
                context.training_version,
                None,
                question_count=20,
                threshold_percent=70,
                feedback_policy="after_final_submission",
            )
            session.add_all([practice_version, final_exam_version])
            await session.flush()

            practice_at = now - timedelta(days=14)
            practice_attempt = make_assessment_attempt(
                context.employee,
                context.assignment,
                practice_version,
                status="completed",
                question_count=10,
                completed_at=practice_at,
            )
            session.add(practice_attempt)
            await session.flush()
            critical_question = make_attempt_question(
                practice_attempt,
                context.question_version,
                is_critical=True,
                provenance_snapshot={
                    "sources": [
                        {
                            "role": "correct_fact",
                            "menu_item_version_allergen_id": str(item_allergen.id),
                        }
                    ]
                },
            )
            session.add(critical_question)
            await session.flush()
            critical_answer = make_submitted_answer(
                practice_attempt,
                critical_question,
                is_correct=False,
                is_critical_error=True,
                submitted_at=practice_at,
            )
            session.add_all(
                [
                    critical_answer,
                    make_attempt_result(
                        practice_attempt,
                        total_count=10,
                        correct_count=3,
                        score_basis_points=3000,
                        pass_status=None,
                        critical_error_count=1,
                        completed_at=practice_at,
                    ),
                ]
            )

            failed_at = now - timedelta(days=12)
            repeated_failed_at = now - timedelta(days=11)
            passed_at = now - timedelta(days=10)
            result_rows = []
            for position, (completed_at, pass_status, correct_count) in enumerate(
                (
                    (failed_at, "failed", 13),
                    (repeated_failed_at, "failed", 12),
                    (passed_at, "passed", 14),
                )
            ):
                attempt = make_assessment_attempt(
                    context.employee,
                    context.assignment,
                    final_exam_version,
                    status="completed",
                    question_count=20,
                    completed_at=completed_at,
                    started_at=completed_at - timedelta(minutes=20),
                    last_activity_at=completed_at,
                    expires_at=completed_at + timedelta(days=7),
                )
                session.add(attempt)
                await session.flush()
                result = make_attempt_result(
                    attempt,
                    total_count=20,
                    correct_count=correct_count,
                    score_basis_points=correct_count * 500,
                    pass_status=pass_status,
                    critical_error_count=0,
                    completed_at=completed_at,
                )
                session.add(result)
                result_rows.append((position, attempt, result))

            second_user = make_user(email_normalized="backfill-second@example.com")
            session.add(second_user)
            await session.flush()
            organization = await session.get(Organization, context.training.organization_id)
            assert organization is not None
            second_membership = make_membership(organization, second_user)
            session.add(second_membership)
            await session.flush()
            second_employee = make_employee_profile(
                second_membership,
                context.training.organization_id,
                location_id=context.training.location_id,
            )
            session.add(second_employee)
            await session.flush()
            second_assignment = make_training_assignment(
                second_employee,
                context.training,
                context.training_version,
            )
            session.add(second_assignment)
            await session.flush()
            second_failed_ids = []
            for completed_at in (now - timedelta(days=9), now - timedelta(days=8)):
                attempt = make_assessment_attempt(
                    second_employee,
                    second_assignment,
                    final_exam_version,
                    status="completed",
                    question_count=20,
                    completed_at=completed_at,
                    started_at=completed_at - timedelta(minutes=20),
                    last_activity_at=completed_at,
                    expires_at=completed_at + timedelta(days=7),
                )
                session.add(attempt)
                await session.flush()
                result = make_attempt_result(
                    attempt,
                    total_count=20,
                    correct_count=11,
                    score_basis_points=5500,
                    pass_status="failed",
                    critical_error_count=0,
                    completed_at=completed_at,
                )
                session.add(result)
                second_failed_ids.append(result.id)

            await session.commit()
            return {
                "critical_answer_id": critical_answer.id,
                "first_failed_result_id": result_rows[0][2].id,
                "completion_attempt_id": result_rows[2][1].id,
                "first_failed_at": failed_at,
                "second_employee_id": second_employee.id,
                "second_first_failed_id": second_failed_ids[0],
                "second_first_failed_at": now - timedelta(days=9),
            }
    finally:
        await engine.dispose()


async def _source_history_snapshot(settings: Settings) -> tuple[tuple[object, ...], ...]:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT attempt.id, attempt.status, attempt.completed_at, "
                    "answer.id, answer.is_correct, answer.is_critical_error, "
                    "result.id, result.pass_status, result.completed_at "
                    "FROM assessment_attempts AS attempt "
                    "LEFT JOIN submitted_answers AS answer ON answer.attempt_id = attempt.id "
                    "LEFT JOIN attempt_results AS result ON result.attempt_id = attempt.id "
                    "ORDER BY attempt.id, answer.id, result.id"
                )
            )
            return tuple(tuple(row) for row in rows)
    finally:
        await engine.dispose()


async def _follow_up_projection_snapshot(
    settings: Settings,
) -> dict[str, tuple[tuple[object, ...], ...]]:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:
            critical = await connection.execute(
                text("SELECT id, submitted_answer_id, subject_key FROM critical_errors ORDER BY id")
            )
            attention = await connection.execute(
                text("SELECT id, case_type, state, subject_key FROM attention_cases ORDER BY id")
            )
            requirements = await connection.execute(
                text(
                    "SELECT id, employee_profile_id, state, source_result_id, "
                    "due_at, completion_attempt_id FROM retake_requirements ORDER BY id"
                )
            )
            return {
                "critical": tuple(tuple(row) for row in critical),
                "attention": tuple(tuple(row) for row in attention),
                "requirements": tuple(tuple(row) for row in requirements),
            }
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
        "assessment_eligibilities",
        "assessment_question_pools",
        "assessment_readiness",
        "assessment_version_translations",
        "assessment_versions",
        "assessments",
        "audit_events",
        "attention_case_actions",
        "attention_case_sources",
        "attention_cases",
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
        "critical_errors",
        "retake_requirement_actions",
        "retake_requirements",
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
def test_candidate_provenance_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        current_columns = asyncio.run(database_column_names(settings, "question_source_links"))
        assert "question_candidate_id" in current_columns

        command.downgrade(config, "0010_interactive_training")
        downgraded_columns = asyncio.run(database_column_names(settings, "question_source_links"))
        assert "question_candidate_id" not in downgraded_columns
        assert "question_version_id" in downgraded_columns
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_question_generation_rule_seed_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0011_candidate_provenance")
        downgraded_rules = asyncio.run(generation_rules(settings))
        assert ("menu.category", 1, "single_choice") not in downgraded_rules

        command.upgrade(config, "head")
        active_rules = asyncio.run(generation_rules(settings))
        assert ("menu.category", 1, "single_choice") in active_rules
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_deterministic_template_seed_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    expected = {
        ("menu.components", 1, "multiple_choice"),
        ("menu.allergens", 1, "recognition"),
        ("menu.description", 1, "recognition"),
    }
    command.upgrade(config, "head")
    try:
        command.downgrade(config, "0012_question_rules")
        downgraded_rules = asyncio.run(generation_rules(settings))
        assert ("menu.category", 1, "single_choice") in downgraded_rules
        assert expected.isdisjoint(downgraded_rules)

        command.upgrade(config, "head")
        active_rules = asyncio.run(generation_rules(settings))
        assert expected <= active_rules
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_practice_persistence_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        current_tables = asyncio.run(database_table_names(settings))
        assert current_tables >= PRACTICE_TABLES
        current_columns = asyncio.run(database_column_names(settings, "assessment_versions"))
        assert "threshold_percent" in current_columns

        command.downgrade(config, "0013_question_templates")
        downgraded_tables = asyncio.run(database_table_names(settings))
        downgraded_columns = asyncio.run(database_column_names(settings, "assessment_versions"))

        assert PRACTICE_TABLES.isdisjoint(downgraded_tables)
        assert "threshold_percent" not in downgraded_columns
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_attention_retakes_migration_downgrades_and_upgrades() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    try:
        current_tables = asyncio.run(database_table_names(settings))
        assert current_tables >= ATTENTION_RETAKE_TABLES

        command.downgrade(config, "0014_practice_persistence")
        downgraded_tables = asyncio.run(database_table_names(settings))

        assert ATTENTION_RETAKE_TABLES.isdisjoint(downgraded_tables)
        assert "assessment_eligibilities" in downgraded_tables
    finally:
        command.upgrade(config, "head")


@pytest.mark.integration
@pytest.mark.migration
def test_attention_retakes_backfill_is_deterministic_and_preserves_sources() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(config, "head")
    asyncio.run(_truncate_backfill_fixture_data(settings))
    command.downgrade(config, "0014_practice_persistence")
    seeded = asyncio.run(_seed_attention_backfill_history(settings))
    source_before = asyncio.run(_source_history_snapshot(settings))

    try:
        command.upgrade(config, "head")
        first_projection = asyncio.run(_follow_up_projection_snapshot(settings))
        source_after = asyncio.run(_source_history_snapshot(settings))

        assert source_after == source_before
        assert len(first_projection["critical"]) == 1
        assert first_projection["critical"][0][1] == seeded["critical_answer_id"]
        assert (
            len([row for row in first_projection["attention"] if row[1] == "critical_allergen"])
            == 1
        )
        assert len(first_projection["requirements"]) == 2

        completed = next(
            row
            for row in first_projection["requirements"]
            if row[3] == seeded["first_failed_result_id"]
        )
        assert completed[2] == "completed"
        assert completed[4] == cast(datetime, seeded["first_failed_at"]) + timedelta(days=7)
        assert completed[5] == seeded["completion_attempt_id"]

        active = next(
            row
            for row in first_projection["requirements"]
            if row[1] == seeded["second_employee_id"]
        )
        assert active[2] == "active"
        assert active[3] == seeded["second_first_failed_id"]
        assert active[4] == cast(datetime, seeded["second_first_failed_at"]) + timedelta(days=7)
        assert any(
            row[1] == "retake_overdue" and row[2] == "open" for row in first_projection["attention"]
        )

        command.downgrade(config, "0014_practice_persistence")
        assert asyncio.run(_source_history_snapshot(settings)) == source_before
        command.upgrade(config, "head")
        second_projection = asyncio.run(_follow_up_projection_snapshot(settings))

        assert second_projection == first_projection
        assert asyncio.run(_source_history_snapshot(settings)) == source_before
    finally:
        command.upgrade(config, "head")
        asyncio.run(_truncate_backfill_fixture_data(settings))
        command.downgrade(config, "0012_question_rules")
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
