from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.models import (
    EmployeeProfile,
    Location,
    OperationalRole,
    Organization,
    OrganizationMembership,
    User,
)


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


def make_employee_profile(
    membership: OrganizationMembership,
    organization_id: UUID,
    **overrides: Any,
) -> EmployeeProfile:
    values: dict[str, Any] = {
        "membership": membership,
        "organization_id": organization_id,
        "first_name": "Марія",
        "last_name": "Коваль",
    }
    values.update(overrides)
    return EmployeeProfile(**values)
