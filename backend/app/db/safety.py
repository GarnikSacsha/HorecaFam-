import re

from sqlalchemy.engine import make_url

from app.core.config import Settings

TEST_DATABASE_PATTERN = re.compile(r"^horeca_test(?:_[a-z0-9]+)*$")


class UnsafeTestDatabaseError(RuntimeError):
    """Raised before any destructive test database operation can run."""


def assert_safe_test_database(settings: Settings) -> None:
    if settings.app_env != "test":
        raise UnsafeTestDatabaseError("Destructive test database access requires APP_ENV=test")

    database_name = make_url(settings.database_url).database
    if database_name is None or TEST_DATABASE_PATTERN.fullmatch(database_name) is None:
        raise UnsafeTestDatabaseError(
            "Destructive test database access requires an explicitly test-scoped database name"
        )
