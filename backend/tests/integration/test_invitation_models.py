from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiIdempotencyRecord, Invitation, InvitationRateLimitBucket
from tests.factories.identity import make_organization, make_user


async def assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_invitation_lifecycle_schema_is_migration_managed(
    db_session: AsyncSession,
) -> None:
    relation_names = (
        "invitations",
        "api_idempotency_records",
        "invitation_rate_limit_buckets",
    )

    for relation_name in relation_names:
        relation = await db_session.scalar(
            text("SELECT to_regclass(:relation_name)"),
            {"relation_name": relation_name},
        )
        assert relation == relation_name


@pytest.mark.integration
async def test_only_one_pending_invitation_exists_per_organization_and_email(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_values = {
        "organization_id": organization.id,
        "email_normalized": "employee@example.com",
        "token_version": 1,
        "token_key_index": 0,
        "status": "pending",
        "invited_by_user_id": inviter.id,
        "expires_at": datetime.now(UTC) + timedelta(hours=72),
    }
    db_session.add_all(
        [
            Invitation(token_hash="a" * 64, **invitation_values),
            Invitation(token_hash="b" * 64, **invitation_values),
        ]
    )

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_idempotency_record_is_unique_within_actor_action_scope(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    actor = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, actor])
    await db_session.flush()
    now = datetime.now(UTC)
    values = {
        "organization_id": organization.id,
        "actor_user_id": actor.id,
        "action": "invitation.create",
        "key": "same-request",
        "request_fingerprint": "c" * 64,
        "resource_type": "invitation",
        "resource_id": organization.id,
        "response_status": 201,
        "expires_at": now + timedelta(hours=24),
    }
    db_session.add_all([ApiIdempotencyRecord(**values), ApiIdempotencyRecord(**values)])

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_invitation_rate_limit_bucket_is_unique_per_action_and_subject(
    db_session: AsyncSession,
) -> None:
    values = {
        "action": "validate",
        "subject_hash": "d" * 64,
        "window_started_at": datetime.now(UTC),
        "request_count": 1,
    }
    db_session.add_all([InvitationRateLimitBucket(**values), InvitationRateLimitBucket(**values)])

    await assert_integrity_error(db_session)
