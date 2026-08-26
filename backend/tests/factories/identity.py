from datetime import UTC, datetime
from typing import Any

from app.models import Location, OperationalRole, Organization, OrganizationMembership, User


def make_organization(**overrides: Any) -> Organization:
    values: dict[str, Any] = {
        "name": "Bacara Test",
        "status": "active",
        "default_locale": "uk",
        "timezone": "Europe/Kyiv",
    }
    values.update(overrides)
    return Organization(**values)


def make_location(organization: Organization, **overrides: Any) -> Location:
    values: dict[str, Any] = {
        "organization": organization,
        "name": "Test Location",
        "status": "active",
        "timezone": "Europe/Kyiv",
    }
    values.update(overrides)
    return Location(**values)


def make_role(organization: Organization, **overrides: Any) -> OperationalRole:
    values: dict[str, Any] = {
        "organization": organization,
        "code": "waiter",
        "name_uk": "Офіціант",
        "status": "active",
    }
    values.update(overrides)
    return OperationalRole(**values)


def make_user(**overrides: Any) -> User:
    values: dict[str, Any] = {
        "email_normalized": "employee@example.com",
        "preferred_locale": "uk",
    }
    values.update(overrides)
    return User(**values)


def make_membership(
    organization: Organization,
    user: User,
    **overrides: Any,
) -> OrganizationMembership:
    values: dict[str, Any] = {
        "organization": organization,
        "user": user,
        "status": "active",
        "activated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return OrganizationMembership(**values)
