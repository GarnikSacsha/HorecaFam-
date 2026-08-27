import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BackgroundJob
from tests.factories import (
    make_background_job,
    make_email_delivery,
    make_invitation,
    make_organization,
    make_user,
)


async def assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_invitation_email_outbox_schema_is_migration_managed(
    db_session: AsyncSession,
) -> None:
    for relation_name in ("background_jobs", "email_deliveries"):
        relation = await db_session.scalar(
            text("SELECT to_regclass(:relation_name)"),
            {"relation_name": relation_name},
        )
        assert relation == relation_name


@pytest.mark.integration
async def test_invitation_job_and_delivery_persist_in_one_organization(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation = make_invitation(organization, inviter)
    db_session.add(invitation)
    await db_session.flush()
    job = make_background_job(organization, invitation)
    db_session.add(job)
    await db_session.flush()
    delivery = make_email_delivery(organization, invitation, job)
    db_session.add(delivery)

    await db_session.commit()

    assert job.payload == {
        "invitation_id": str(invitation.id),
        "token_version": invitation.token_version,
    }
    assert delivery.organization_id == invitation.organization_id


@pytest.mark.integration
async def test_background_job_is_unique_per_type_and_idempotency_key(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation = make_invitation(organization, inviter)
    db_session.add(invitation)
    await db_session.flush()
    first_job = make_background_job(organization, invitation)
    second_job = make_background_job(organization, invitation)
    db_session.add_all([first_job, second_job])

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_invitation_job_payload_requires_reconstructable_identity_fields(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    db_session.add(
        BackgroundJob(
            organization_id=organization.id,
            job_type="invitation_email",
            status="pending",
            payload={"unexpected": "value"},
            idempotency_key="invalid-payload",
        )
    )

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_email_delivery_rejects_cross_organization_source(
    db_session: AsyncSession,
) -> None:
    organization_a = make_organization(name="Organization A")
    organization_b = make_organization(name="Organization B")
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization_a, organization_b, inviter])
    await db_session.flush()
    invitation = make_invitation(organization_a, inviter)
    db_session.add(invitation)
    await db_session.flush()
    job = make_background_job(organization_a, invitation)
    db_session.add(job)
    await db_session.flush()
    db_session.add(make_email_delivery(organization_b, invitation, job))

    await assert_integrity_error(db_session)
