from alembic import command
from alembic.config import Config

from tests.migration.test_migrations import BACKEND_ROOT, database_settings


def test_cycle_migration_round_trip_and_no_metadata_drift() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.downgrade(config, "0020_menu_change_history")
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    command.check(config)


def test_empty_test_schema_upgrades_with_cycle_constraints() -> None:
    settings = database_settings()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    command.check(config)
