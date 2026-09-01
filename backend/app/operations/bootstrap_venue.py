import argparse
import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.email import normalize_email
from app.db.session import create_engine, create_session_factory
from app.models import AdminAccess, AuditEvent, Location, OperationalRole, Organization, User

_ROLE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SUPPORTED_PILOT_TIMEZONES = frozenset({"Europe/Kyiv"})


class BootstrapValidationError(ValueError):
    pass


class BootstrapConflictError(ValueError):
    pass


class BootstrapVenueSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    idempotency_key: str = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_-]+$")
    operator_email: EmailStr
    organization_name: str = Field(min_length=1, max_length=255)
    location_name: str = Field(min_length=1, max_length=255)
    location_address: str | None = Field(default=None, max_length=500)
    timezone: str = Field(min_length=1, max_length=64)
    role_code: str = Field(min_length=1, max_length=64)
    role_name_uk: str = Field(min_length=1, max_length=255)

    @field_validator("organization_name", "location_name", "role_name_uk")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Name must not be blank")
        return normalized

    @field_validator("location_address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("operator_email")
    @classmethod
    def normalize_operator_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if _ROLE_CODE.fullmatch(normalized) is None:
            raise ValueError("Role code must be a normalized machine identifier")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        # Пілот навмисно обмежений одним погодженим часовим поясом без зовнішньої tzdata.
        if normalized not in _SUPPORTED_PILOT_TIMEZONES:
            raise ValueError("Timezone is outside the approved pilot set")
        return normalized


class BootstrapVenueResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["planned", "created", "existing"]
    fingerprint: str
    organization_id: UUID | None = None
    location_id: UUID | None = None
    role_id: UUID | None = None
    organization_admin_access_id: UUID | None = None


def _fingerprint(spec: BootstrapVenueSpec) -> str:
    canonical = json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _advisory_lock_key(idempotency_key: str) -> int:
    unsigned = int.from_bytes(hashlib.sha256(idempotency_key.encode()).digest()[:8], "big")
    return unsigned if unsigned < 2**63 else unsigned - 2**64


async def _operator_user(db: AsyncSession, email: str) -> User:
    user = await db.scalar(
        select(User)
        .join(AdminAccess, AdminAccess.user_id == User.id)
        .where(
            User.email_normalized == email,
            AdminAccess.scope == "platform_operator",
            AdminAccess.status == "active",
        )
    )
    if user is None:
        raise BootstrapValidationError("An active Platform Operator is required")
    return user


async def _existing_result(
    db: AsyncSession,
    *,
    spec: BootstrapVenueSpec,
    fingerprint: str,
) -> BootstrapVenueResult | None:
    event = await db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "venue_bootstrapped",
            AuditEvent.new_values["bootstrap_key"].astext == spec.idempotency_key,
        )
    )
    if event is None:
        return None
    values = event.new_values or {}
    if values.get("fingerprint") != fingerprint:
        raise BootstrapConflictError("Bootstrap key was already used for different input")
    if event.target_id is None:
        raise BootstrapConflictError("Bootstrap audit record is incomplete")
    return BootstrapVenueResult(
        status="existing",
        fingerprint=fingerprint,
        organization_id=event.target_id,
        location_id=UUID(str(values["location_id"])),
        role_id=UUID(str(values["role_id"])),
        organization_admin_access_id=UUID(str(values["organization_admin_access_id"])),
    )


async def bootstrap_venue(
    db: AsyncSession,
    *,
    spec: BootstrapVenueSpec,
    apply: bool,
    now: datetime | None = None,
) -> BootstrapVenueResult:
    operator = await _operator_user(db, str(spec.operator_email))
    fingerprint = _fingerprint(spec)
    if apply:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _advisory_lock_key(spec.idempotency_key)},
        )
    existing = await _existing_result(db, spec=spec, fingerprint=fingerprint)
    if existing is not None:
        return existing
    if not apply:
        return BootstrapVenueResult(status="planned", fingerprint=fingerprint)

    organization = Organization(
        name=spec.organization_name,
        status="active",
        default_locale="uk",
        timezone=spec.timezone,
    )
    location = Location(
        organization=organization,
        name=spec.location_name,
        address=spec.location_address,
        status="active",
        timezone=spec.timezone,
    )
    role = OperationalRole(
        organization=organization,
        code=spec.role_code,
        name_uk=spec.role_name_uk,
        status="active",
    )
    db.add_all([organization, location, role])
    await db.flush()
    access = AdminAccess(
        user_id=operator.id,
        scope="organization_admin",
        organization_id=organization.id,
        status="active",
        granted_by_user_id=operator.id,
        granted_at=now or datetime.now(UTC),
    )
    db.add(access)
    await db.flush()
    db.add(
        AuditEvent(
            organization_id=organization.id,
            actor_user_id=operator.id,
            actor_type="user",
            action="venue_bootstrapped",
            target_type="organization",
            target_id=organization.id,
            old_values=None,
            new_values={
                "bootstrap_key": spec.idempotency_key,
                "fingerprint": fingerprint,
                "location_id": str(location.id),
                "role_id": str(role.id),
                "organization_admin_access_id": str(access.id),
            },
            request_id=uuid4(),
            outcome="success",
            error_code=None,
            created_at=now or datetime.now(UTC),
        )
    )
    await db.flush()
    return BootstrapVenueResult(
        status="created",
        fingerprint=fingerprint,
        organization_id=organization.id,
        location_id=location.id,
        role_id=role.id,
        organization_admin_access_id=access.id,
    )


async def _run(spec: BootstrapVenueSpec, *, apply: bool) -> BootstrapVenueResult:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session, session.begin():
            return await bootstrap_venue(session, spec=spec, apply=apply)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or apply one bounded venue bootstrap")
    parser.add_argument("--spec", required=True, help="Path to a non-secret JSON bootstrap spec")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-environment")
    arguments = parser.parse_args()
    settings = get_settings()
    if arguments.apply and arguments.confirm_environment != settings.app_env:
        parser.error("--apply requires --confirm-environment matching APP_ENV")
    with open(arguments.spec, encoding="utf-8") as source:
        spec = BootstrapVenueSpec.model_validate_json(source.read())
    result = asyncio.run(_run(spec, apply=arguments.apply))
    print(result.model_dump_json())


if __name__ == "__main__":
    main()
