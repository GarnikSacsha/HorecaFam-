import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import APIError
from app.db.session import create_engine, create_session_factory
from app.models import (
    AuditEvent,
    EmployeeProfile,
    Invitation,
    OrganizationMembership,
    Session,
    User,
)
from app.security.invitation_tokens import InvitationTokenManager
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.invitation_acceptance import (
    InvitationAcceptanceOutcome,
    accept_invitation,
)
from tests.factories import make_invitation, make_membership, make_organization, make_user

FIXED_NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)


async def make_invitation_with_token(
    db_session: AsyncSession,
    auth_settings: Settings,
    *,
    email: str,
) -> tuple[Invitation, str]:
    organization = make_organization(name=f"Concurrency {uuid4()}")
    inviter = make_user(email_normalized=f"race-inviter-{uuid4()}@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    manager = InvitationTokenManager(auth_settings.invitation_token_hmac_keys)
    raw_token = manager.derive(invitation_id, token_version=1, key_index=0)
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        email_normalized=email,
        token_hash=hash_secret(raw_token),
        expires_at=FIXED_NOW + timedelta(hours=72),
    )
    db_session.add(invitation)
    await db_session.flush()
    return invitation, raw_token


async def accept_in_independent_session(
    session_factory: async_sessionmaker[AsyncSession],
    auth_settings: Settings,
    *,
    raw_token: str,
) -> InvitationAcceptanceOutcome | APIError | Exception:
    async with session_factory() as session:
        try:
            return await accept_invitation(
                session,
                raw_token=raw_token,
                acceptance_mode="activate_access",
                password="correct horse battery staple",
                settings=auth_settings,
                passwords=PasswordManager(),
                now=FIXED_NOW,
                request_id=uuid4(),
                user_agent="concurrency-test",
            )
        except Exception as exception:
            return exception


async def acceptance_counts(
    db_session: AsyncSession,
    *,
    email: str,
    organization_ids: set[UUID],
) -> dict[str, int]:
    await db_session.rollback()
    return {
        "users": int(
            await db_session.scalar(
                select(func.count()).select_from(User).where(User.email_normalized == email)
            )
            or 0
        ),
        "memberships": int(
            await db_session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(OrganizationMembership.organization_id.in_(organization_ids))
            )
            or 0
        ),
        "profiles": int(
            await db_session.scalar(select(func.count()).select_from(EmployeeProfile)) or 0
        ),
        "sessions": int(await db_session.scalar(select(func.count()).select_from(Session)) or 0),
        "audits": int(
            await db_session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "invitation_accepted")
            )
            or 0
        ),
    }


@pytest.mark.integration
async def test_concurrent_same_token_has_one_winner_and_one_consumed_conflict(
    db_session: AsyncSession,
    auth_settings: Settings,
    migrated_test_database: Settings,
) -> None:
    invitation, raw_token = await make_invitation_with_token(
        db_session,
        auth_settings,
        email="same-token-race@example.com",
    )
    await db_session.commit()
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)

    try:
        results = await asyncio.gather(
            accept_in_independent_session(
                session_factory,
                auth_settings,
                raw_token=raw_token,
            ),
            accept_in_independent_session(
                session_factory,
                auth_settings,
                raw_token=raw_token,
            ),
        )
    finally:
        await engine.dispose()

    successes = [result for result in results if isinstance(result, InvitationAcceptanceOutcome)]
    errors = [result for result in results if isinstance(result, APIError)]
    assert len(successes) == 1
    assert [error.code for error in errors] == ["INVITATION_ALREADY_ACCEPTED"]
    assert await acceptance_counts(
        db_session,
        email="same-token-race@example.com",
        organization_ids={invitation.organization_id},
    ) == {
        "users": 1,
        "memberships": 1,
        "profiles": 1,
        "sessions": 1,
        "audits": 1,
    }


@pytest.mark.integration
async def test_concurrent_new_user_invitations_do_not_duplicate_or_overwrite_identity(
    db_session: AsyncSession,
    auth_settings: Settings,
    migrated_test_database: Settings,
) -> None:
    email = "same-global-user-race@example.com"
    first_invitation, first_token = await make_invitation_with_token(
        db_session,
        auth_settings,
        email=email,
    )
    second_invitation, second_token = await make_invitation_with_token(
        db_session,
        auth_settings,
        email=email,
    )
    await db_session.commit()
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)

    try:
        results = await asyncio.gather(
            accept_in_independent_session(
                session_factory,
                auth_settings,
                raw_token=first_token,
            ),
            accept_in_independent_session(
                session_factory,
                auth_settings,
                raw_token=second_token,
            ),
        )
    finally:
        await engine.dispose()

    successes = [result for result in results if isinstance(result, InvitationAcceptanceOutcome)]
    errors = [result for result in results if isinstance(result, APIError)]
    assert len(successes) == 1
    assert [error.code for error in errors] == ["INVITATION_ACCEPTANCE_MODE_CHANGED"]
    assert await acceptance_counts(
        db_session,
        email=email,
        organization_ids={first_invitation.organization_id, second_invitation.organization_id},
    ) == {
        "users": 1,
        "memberships": 1,
        "profiles": 1,
        "sessions": 1,
        "audits": 1,
    }
    invitation_statuses = set(
        (
            await db_session.scalars(
                select(Invitation.status).where(
                    Invitation.id.in_([first_invitation.id, second_invitation.id])
                )
            )
        ).all()
    )
    assert invitation_statuses == {"pending", "accepted"}


@pytest.mark.integration
async def test_existing_user_acceptance_preserves_other_organization_profile(
    db_session: AsyncSession,
    auth_settings: Settings,
) -> None:
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized="tenant-isolation@example.com",
        password_hash=passwords.hash("existing account password"),
    )
    original_organization = make_organization(name="Original tenant")
    db_session.add_all([existing_user, original_organization])
    await db_session.flush()
    original_membership = make_membership(original_organization, existing_user)
    db_session.add(original_membership)
    await db_session.flush()
    original_profile = EmployeeProfile(
        membership_id=original_membership.id,
        organization_id=original_organization.id,
        first_name="Original",
        last_name="Profile",
    )
    db_session.add(original_profile)
    await db_session.commit()
    invitation, raw_token = await make_invitation_with_token(
        db_session,
        auth_settings,
        email=existing_user.email_normalized,
    )
    await db_session.commit()

    outcome = await accept_invitation(
        db_session,
        raw_token=raw_token,
        acceptance_mode="accept_existing_account",
        password="existing account password",
        settings=auth_settings,
        passwords=passwords,
        now=FIXED_NOW,
        request_id=uuid4(),
        user_agent=None,
    )

    await db_session.refresh(original_membership)
    await db_session.refresh(original_profile)
    assert original_membership.status == "active"
    assert original_profile.first_name == "Original"
    assert original_profile.last_name == "Profile"
    assert original_profile.organization_id == original_organization.id
    assert outcome.membership.organization_id == invitation.organization_id
    assert outcome.membership.status == "pending"
    assert outcome.profile.organization_id == invitation.organization_id
    assert outcome.profile.first_name is None
    assert outcome.profile.last_name is None
