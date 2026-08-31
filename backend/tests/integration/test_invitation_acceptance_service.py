from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.models import (
    AuditEvent,
    AuthRateLimitBucket,
    EmployeeProfile,
    Invitation,
    Organization,
    OrganizationMembership,
    Session,
    User,
)
from app.security.invitation_tokens import InvitationTokenManager
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.invitation_acceptance import accept_invitation
from tests.factories import (
    make_admin_access,
    make_invitation,
    make_membership,
    make_organization,
    make_user,
)

FIXED_NOW = datetime(2030, 8, 27, 9, 30, tzinfo=UTC)


async def arrange_invitation(
    db_session: AsyncSession,
    auth_settings: Settings,
    *,
    invited_email: str,
) -> tuple[Invitation, str]:
    organization = make_organization(name="Acceptance organization")
    inviter = make_user(email_normalized=f"inviter-{uuid4()}@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    token_manager = InvitationTokenManager(auth_settings.invitation_token_hmac_keys)
    raw_token = token_manager.derive(invitation_id, token_version=1, key_index=0)
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        email_normalized=invited_email,
        token_hash=hash_secret(raw_token),
        expires_at=FIXED_NOW + timedelta(hours=72),
    )
    db_session.add(invitation)
    await db_session.commit()
    return invitation, raw_token


@pytest.mark.integration
async def test_new_user_acceptance_commits_complete_pending_identity_and_session(
    db_session: AsyncSession,
    auth_settings: Settings,
) -> None:
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email="new-employee@example.com",
    )
    organization_id = invitation.organization_id
    passwords = PasswordManager()

    outcome = await accept_invitation(
        db_session,
        raw_token=raw_token,
        acceptance_mode="activate_access",
        password="correct horse battery staple",
        settings=auth_settings,
        passwords=passwords,
        now=FIXED_NOW,
        request_id=uuid4(),
        user_agent="Stage 4 integration test",
    )

    user = await db_session.scalar(
        select(User).where(User.email_normalized == "new-employee@example.com")
    )
    assert user is not None
    assert user.email_verified_at == FIXED_NOW
    assert user.password_hash is not None
    assert passwords.verify(user.password_hash, "correct horse battery staple")
    membership = await db_session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    assert membership is not None
    assert membership.status == "pending"
    assert membership.activated_at is None
    assert membership.disabled_at is None
    profile = await db_session.scalar(
        select(EmployeeProfile).where(EmployeeProfile.membership_id == membership.id)
    )
    assert profile is not None
    assert profile.organization_id == organization_id
    assert profile.first_name is None
    assert profile.last_name is None
    assert profile.operational_role_id is None
    assert profile.location_id is None
    accepted = await db_session.get(Invitation, invitation.id)
    assert accepted is not None
    assert accepted.status == "accepted"
    assert accepted.accepted_at == FIXED_NOW
    session = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert session is not None
    assert session.mfa_verified_at is None
    assert session.absolute_expires_at == FIXED_NOW + timedelta(days=90)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "invitation_accepted")
        )
        == 1
    )
    assert outcome.acceptance_mode == "activate_access"
    assert outcome.user.id == user.id
    assert outcome.membership.id == membership.id
    assert outcome.profile.id == profile.id
    assert outcome.session.record.id == session.id


@pytest.mark.integration
async def test_existing_user_acceptance_reuses_identity_and_issues_pending_session(
    db_session: AsyncSession,
    auth_settings: Settings,
) -> None:
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized="existing-employee@example.com",
        password_hash=passwords.hash("existing account password"),
        email_verified_at=FIXED_NOW - timedelta(days=30),
    )
    db_session.add(existing_user)
    await db_session.commit()
    existing_user_id = existing_user.id
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email=existing_user.email_normalized,
    )

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

    users = list(
        (
            await db_session.scalars(
                select(User).where(User.email_normalized == existing_user.email_normalized)
            )
        ).all()
    )
    assert [user.id for user in users] == [existing_user_id]
    assert outcome.user.id == existing_user_id
    assert outcome.membership.organization_id == invitation.organization_id
    assert outcome.membership.status == "pending"
    assert outcome.profile.membership_id == outcome.membership.id
    assert outcome.session.record.absolute_expires_at == FIXED_NOW + timedelta(days=90)
    assert outcome.session.record.mfa_verified_at is None


@pytest.mark.integration
async def test_existing_admin_acceptance_uses_strict_lifetime_without_mfa_proof(
    db_session: AsyncSession,
    auth_settings: Settings,
) -> None:
    passwords = PasswordManager()
    admin = make_user(
        email_normalized="existing-admin@example.com",
        password_hash=passwords.hash("admin account password"),
    )
    db_session.add(admin)
    await db_session.flush()
    db_session.add(make_admin_access(admin, scope="platform_operator"))
    await db_session.commit()
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email=admin.email_normalized,
    )

    outcome = await accept_invitation(
        db_session,
        raw_token=raw_token,
        acceptance_mode="accept_existing_account",
        password="admin account password",
        settings=auth_settings,
        passwords=passwords,
        now=FIXED_NOW,
        request_id=uuid4(),
        user_agent=None,
    )

    assert outcome.membership.organization_id == invitation.organization_id
    assert outcome.session.record.absolute_expires_at == FIXED_NOW + timedelta(days=30)
    assert outcome.session.record.mfa_verified_at is None


@pytest.mark.integration
async def test_wrong_existing_password_records_throttle_and_rolls_back_business_state(
    db_session: AsyncSession,
    auth_settings: Settings,
) -> None:
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized="wrong-password@example.com",
        password_hash=passwords.hash("correct password"),
    )
    db_session.add(existing_user)
    await db_session.commit()
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email=existing_user.email_normalized,
    )

    with pytest.raises(APIError) as exc_info:
        await accept_invitation(
            db_session,
            raw_token=raw_token,
            acceptance_mode="accept_existing_account",
            password="wrong password",
            settings=auth_settings,
            passwords=passwords,
            now=FIXED_NOW,
            request_id=uuid4(),
            user_agent=None,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_CREDENTIALS"
    await db_session.refresh(invitation)
    assert invitation.status == "pending"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(OrganizationMembership.organization_id == invitation.organization_id)
        )
        == 0
    )
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0
    bucket = await db_session.scalar(select(AuthRateLimitBucket))
    assert bucket is not None
    assert bucket.failure_count == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("membership_status", "expected_code"),
    [
        ("active", "MEMBERSHIP_ALREADY_ACTIVE"),
        ("disabled", "MEMBERSHIP_DISABLED"),
    ],
)
async def test_existing_membership_conflicts_leave_invitation_pending(
    db_session: AsyncSession,
    auth_settings: Settings,
    membership_status: str,
    expected_code: str,
) -> None:
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized=f"{membership_status}-member@example.com",
        password_hash=passwords.hash("existing password"),
    )
    db_session.add(existing_user)
    await db_session.commit()
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email=existing_user.email_normalized,
    )
    organization = await db_session.get(Organization, invitation.organization_id)
    assert organization is not None
    membership_values: dict[str, Any] = {"status": membership_status}
    if membership_status == "disabled":
        membership_values.update(activated_at=None, disabled_at=FIXED_NOW)
    db_session.add(make_membership(organization, existing_user, **membership_values))
    await db_session.commit()

    with pytest.raises(APIError) as exc_info:
        await accept_invitation(
            db_session,
            raw_token=raw_token,
            acceptance_mode="accept_existing_account",
            password="existing password",
            settings=auth_settings,
            passwords=passwords,
            now=FIXED_NOW,
            request_id=uuid4(),
            user_agent=None,
        )

    assert exc_info.value.code == expected_code
    await db_session.refresh(invitation)
    assert invitation.status == "pending"
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.integration
async def test_stale_acceptance_mode_has_zero_mutation(
    db_session: AsyncSession,
    auth_settings: Settings,
) -> None:
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized="stale-mode@example.com",
        password_hash=passwords.hash("existing password"),
    )
    db_session.add(existing_user)
    await db_session.commit()
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email=existing_user.email_normalized,
    )

    with pytest.raises(APIError) as exc_info:
        await accept_invitation(
            db_session,
            raw_token=raw_token,
            acceptance_mode="activate_access",
            password="new credential must not replace old",
            settings=auth_settings,
            passwords=passwords,
            now=FIXED_NOW,
            request_id=uuid4(),
            user_agent=None,
        )

    assert exc_info.value.code == "INVITATION_ACCEPTANCE_MODE_CHANGED"
    await db_session.refresh(invitation)
    assert invitation.status == "pending"
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(OrganizationMembership.organization_id == invitation.organization_id)
        )
        == 0
    )


@pytest.mark.integration
async def test_session_failure_rolls_back_new_user_membership_profile_and_acceptance(
    db_session: AsyncSession,
    auth_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email="rollback@example.com",
    )
    invitation_id = invitation.id

    async def fail_session(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("synthetic session failure")

    monkeypatch.setattr(
        "app.services.invitation_acceptance.create_session",
        fail_session,
    )
    with pytest.raises(RuntimeError, match="synthetic session failure"):
        await accept_invitation(
            db_session,
            raw_token=raw_token,
            acceptance_mode="activate_access",
            password="correct horse battery staple",
            settings=auth_settings,
            passwords=PasswordManager(),
            now=FIXED_NOW,
            request_id=uuid4(),
            user_agent=None,
        )

    invitation_after = await db_session.get(Invitation, invitation_id)
    assert invitation_after is not None
    assert invitation_after.status == "pending"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email_normalized == "rollback@example.com")
        )
        == 0
    )
    assert await db_session.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
    assert await db_session.scalar(select(func.count()).select_from(EmployeeProfile)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "invitation_accepted")
        )
        == 0
    )


@pytest.mark.integration
async def test_acceptance_audit_failure_rolls_back_session_and_business_state(
    db_session: AsyncSession,
    auth_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invitation, raw_token = await arrange_invitation(
        db_session,
        auth_settings,
        invited_email="audit-rollback@example.com",
    )
    invitation_id = invitation.id

    def fail_acceptance_audit(*_args: Any, **_kwargs: Any) -> AuditEvent:
        raise RuntimeError("synthetic acceptance audit failure")

    monkeypatch.setattr(
        "app.services.invitation_acceptance.AuditEvent",
        fail_acceptance_audit,
    )
    with pytest.raises(RuntimeError, match="synthetic acceptance audit failure"):
        await accept_invitation(
            db_session,
            raw_token=raw_token,
            acceptance_mode="activate_access",
            password="correct horse battery staple",
            settings=auth_settings,
            passwords=PasswordManager(),
            now=FIXED_NOW,
            request_id=uuid4(),
            user_agent=None,
        )

    invitation_after = await db_session.get(Invitation, invitation_id)
    assert invitation_after is not None
    assert invitation_after.status == "pending"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email_normalized == "audit-rollback@example.com")
        )
        == 0
    )
    assert await db_session.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
    assert await db_session.scalar(select(func.count()).select_from(EmployeeProfile)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0
