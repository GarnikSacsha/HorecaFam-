from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAccess, AuditEvent, Location, OperationalRole, Organization
from app.operations.bootstrap_venue import (
    BootstrapConflictError,
    BootstrapVenueSpec,
    bootstrap_venue,
)
from tests.factories.auth import make_admin_access
from tests.factories.identity import make_user


def make_spec(**overrides: object) -> BootstrapVenueSpec:
    values: dict[str, object] = {
        "idempotency_key": "pilot-venue-1",
        "operator_email": "operator@example.com",
        "organization_name": "Synthetic Pilot Venue",
        "location_name": "Synthetic Main Location",
        "timezone": "Europe/Kyiv",
        "role_code": "waiter",
        "role_name_uk": "Офіціант",
    }
    values.update(overrides)
    return BootstrapVenueSpec.model_validate(values)


def test_bootstrap_input_rejects_unknown_timezone_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        make_spec(timezone="Mars/Olympus", hidden_secret="not-allowed")


@pytest.mark.integration
async def test_bootstrap_dry_run_validates_operator_without_mutating(
    db_session: AsyncSession,
) -> None:
    operator = make_user(email_normalized="operator@example.com")
    db_session.add(operator)
    await db_session.flush()
    db_session.add(make_admin_access(operator, scope="platform_operator"))
    await db_session.commit()

    result = await bootstrap_venue(
        db_session,
        spec=make_spec(),
        apply=False,
        now=datetime(2031, 1, 1, tzinfo=UTC),
    )

    assert result.status == "planned"
    assert result.organization_id is None
    assert await db_session.scalar(select(func.count()).select_from(Organization)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


@pytest.mark.integration
async def test_bootstrap_apply_is_idempotent_and_audited(
    db_session: AsyncSession,
) -> None:
    operator = make_user(email_normalized="operator@example.com")
    db_session.add(operator)
    await db_session.flush()
    db_session.add(make_admin_access(operator, scope="platform_operator"))
    await db_session.commit()
    now = datetime(2031, 1, 1, tzinfo=UTC)

    created = await bootstrap_venue(db_session, spec=make_spec(), apply=True, now=now)
    await db_session.commit()
    replayed = await bootstrap_venue(db_session, spec=make_spec(), apply=True, now=now)
    await db_session.commit()

    assert created.status == "created"
    assert replayed.status == "existing"
    assert replayed == created.model_copy(update={"status": "existing"})
    assert await db_session.scalar(select(func.count()).select_from(Organization)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Location)) == 1
    assert await db_session.scalar(select(func.count()).select_from(OperationalRole)) == 1
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AdminAccess)
            .where(AdminAccess.scope == "organization_admin")
        )
        == 1
    )
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "venue_bootstrapped")
    )
    assert audit is not None
    assert audit.actor_user_id == operator.id
    assert audit.organization_id == created.organization_id
    assert audit.new_values == {
        "bootstrap_key": "pilot-venue-1",
        "fingerprint": created.fingerprint,
        "location_id": str(created.location_id),
        "role_id": str(created.role_id),
        "organization_admin_access_id": str(created.organization_admin_access_id),
    }

    with pytest.raises(BootstrapConflictError):
        await bootstrap_venue(
            db_session,
            spec=make_spec(organization_name="Different Venue"),
            apply=True,
            now=now,
        )
