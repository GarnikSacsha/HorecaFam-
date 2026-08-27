from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.models import (
    AdminAccess,
    AuditEvent,
    EmployeeProfile,
    Invitation,
    InvitationRateLimitBucket,
    Organization,
    OrganizationMembership,
    User,
)
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.auth import authenticate_password
from app.services.invitations import VALIDATE_FAILURE_LIMIT, consume_invitation_rate_limit
from app.services.sessions import IssuedSession, create_session

AcceptanceMode = Literal["activate_access", "accept_existing_account"]


@dataclass(frozen=True)
class InvitationAcceptanceOutcome:
    acceptance_mode: AcceptanceMode
    invitation: Invitation
    user: User
    membership: OrganizationMembership
    profile: EmployeeProfile
    session: IssuedSession


def _lifecycle_error(invitation: Invitation | None, *, now: datetime) -> APIError | None:
    if invitation is None:
        return APIError(
            status_code=404,
            code="INVITATION_NOT_FOUND",
            message="Запрошення не знайдено.",
        )
    if invitation.status == "revoked":
        return APIError(
            status_code=410,
            code="INVITATION_REVOKED",
            message="Запрошення відкликано.",
        )
    if invitation.status == "accepted":
        return APIError(
            status_code=409,
            code="INVITATION_ALREADY_ACCEPTED",
            message="Запрошення вже використано.",
        )
    if invitation.expires_at <= now:
        return APIError(
            status_code=410,
            code="INVITATION_EXPIRED",
            message="Строк дії запрошення минув.",
        )
    return None


def _acceptance_mode_changed() -> APIError:
    return APIError(
        status_code=409,
        code="INVITATION_ACCEPTANCE_MODE_CHANGED",
        message="Режим прийняття запрошення змінився. Перевірте запрошення ще раз.",
    )


async def _accept_invitation(
    db: AsyncSession,
    *,
    raw_token: str,
    acceptance_mode: AcceptanceMode,
    password: str,
    settings: Settings,
    passwords: PasswordManager,
    now: datetime,
    request_id: UUID,
    user_agent: str | None,
) -> InvitationAcceptanceOutcome:
    settings.validate_auth_security()
    settings.validate_invitation_security()
    token_hash = hash_secret(raw_token)
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
    )
    lifecycle_error = _lifecycle_error(invitation, now=now)
    if lifecycle_error is not None:
        await consume_invitation_rate_limit(
            db,
            action="validate",
            subject_hash=token_hash,
            limit=VALIDATE_FAILURE_LIMIT,
            now=now,
        )
        raise lifecycle_error
    if invitation is None:
        raise RuntimeError("Invitation lifecycle validation returned an impossible result")

    user = await db.scalar(
        select(User).where(User.email_normalized == invitation.email_normalized).with_for_update()
    )
    if acceptance_mode == "activate_access":
        if user is not None:
            raise _acceptance_mode_changed()
        organization_locale = await db.scalar(
            select(Organization.default_locale).where(Organization.id == invitation.organization_id)
        )
        if organization_locale is None:
            raise RuntimeError("Invitation Organization is unavailable")
        user = User(
            email_normalized=invitation.email_normalized,
            password_hash=passwords.hash(password),
            preferred_locale=organization_locale,
            email_verified_at=now,
        )
        db.add(user)
        await db.flush()
    else:
        if user is None:
            raise _acceptance_mode_changed()
        user = await authenticate_password(
            db,
            email=invitation.email_normalized,
            password=password,
            settings=settings,
            passwords=passwords,
            now=now,
            lock_user=True,
        )

    membership = await db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == invitation.organization_id,
            OrganizationMembership.user_id == user.id,
        )
        .with_for_update()
    )
    if membership is not None and membership.status == "active":
        raise APIError(
            status_code=409,
            code="MEMBERSHIP_ALREADY_ACTIVE",
            message="Користувач уже має активний доступ.",
        )
    if membership is not None and membership.status == "disabled":
        raise APIError(
            status_code=409,
            code="MEMBERSHIP_DISABLED",
            message="Доступ користувача вимкнено.",
        )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            status="pending",
        )
        db.add(membership)
        await db.flush()
    profile = await db.scalar(
        select(EmployeeProfile)
        .where(EmployeeProfile.membership_id == membership.id)
        .with_for_update()
    )
    if profile is None:
        profile = EmployeeProfile(
            membership_id=membership.id,
            organization_id=invitation.organization_id,
        )
        db.add(profile)
    invitation.status = "accepted"
    invitation.accepted_at = now

    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    has_elevated_access = (
        await db.scalar(
            select(AdminAccess.id).where(
                AdminAccess.user_id == user.id,
                AdminAccess.status == "active",
            )
        )
        is not None
    )
    issued_session = await create_session(
        db,
        user=user,
        now=now,
        hmac_key=hmac_key,
        has_elevated_access=has_elevated_access,
        mfa_verified=False,
        request_id=request_id,
        user_agent=user_agent,
    )
    validation_bucket = await db.scalar(
        select(InvitationRateLimitBucket).where(
            InvitationRateLimitBucket.action == "validate",
            InvitationRateLimitBucket.subject_hash == token_hash,
        )
    )
    if validation_bucket is not None:
        await db.delete(validation_bucket)
    db.add(
        AuditEvent(
            organization_id=invitation.organization_id,
            actor_user_id=user.id,
            actor_type="user",
            action="invitation_accepted",
            target_type="invitation",
            target_id=invitation.id,
            request_id=request_id,
            outcome="success",
            old_values={"status": "pending"},
            new_values={
                "status": "accepted",
                "acceptance_mode": acceptance_mode,
            },
        )
    )
    await db.commit()
    return InvitationAcceptanceOutcome(
        acceptance_mode=acceptance_mode,
        invitation=invitation,
        user=user,
        membership=membership,
        profile=profile,
        session=issued_session,
    )


async def accept_invitation(
    db: AsyncSession,
    *,
    raw_token: str,
    acceptance_mode: AcceptanceMode,
    password: str,
    settings: Settings,
    passwords: PasswordManager,
    now: datetime,
    request_id: UUID,
    user_agent: str | None,
) -> InvitationAcceptanceOutcome:
    try:
        return await _accept_invitation(
            db,
            raw_token=raw_token,
            acceptance_mode=acceptance_mode,
            password=password,
            settings=settings,
            passwords=passwords,
            now=now,
            request_id=request_id,
            user_agent=user_agent,
        )
    except Exception:
        await db.rollback()
        raise
