import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AdminAccess, AuditEvent, OrganizationMembership, Session, User
from app.schemas.auth import OrganizationAccess, SessionInfo, SessionResponse, SessionUser
from app.security.tokens import generate_opaque_token, hash_secret

SESSION_INACTIVITY = timedelta(days=14)
EMPLOYEE_SESSION_LIFETIME = timedelta(days=90)
ELEVATED_SESSION_LIFETIME = timedelta(days=30)


@dataclass(frozen=True)
class IssuedSession:
    record: Session
    raw_token: str
    csrf_token: str


def derive_csrf_token(raw_session_token: str, hmac_key: SecretStr) -> str:
    return hmac.new(
        hmac_key.get_secret_value().encode("utf-8"),
        f"csrf:{raw_session_token}".encode(),
        hashlib.sha256,
    ).hexdigest()


async def create_session(
    db: AsyncSession,
    *,
    user: User,
    now: datetime,
    hmac_key: SecretStr,
    elevated: bool,
    request_id: UUID,
    user_agent: str | None,
) -> IssuedSession:
    raw_token = generate_opaque_token()
    csrf_token = derive_csrf_token(raw_token, hmac_key)
    lifetime = ELEVATED_SESSION_LIFETIME if elevated else EMPLOYEE_SESSION_LIFETIME
    record = Session(
        user_id=user.id,
        token_hash=hash_secret(raw_token),
        csrf_token_hash=hash_secret(csrf_token),
        last_seen_at=now,
        absolute_expires_at=now + lifetime,
        mfa_verified_at=now if elevated else None,
        user_agent=user_agent[:512] if user_agent else None,
    )
    db.add(record)
    await db.flush()
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            actor_type="user",
            action="session_created",
            target_type="session",
            target_id=record.id,
            request_id=request_id,
            outcome="success",
        )
    )
    return IssuedSession(record=record, raw_token=raw_token, csrf_token=csrf_token)


async def build_session_response(
    db: AsyncSession,
    *,
    issued_session: Session,
    user: User,
    raw_token: str,
    hmac_key: SecretStr,
) -> SessionResponse:
    memberships = list(
        (
            await db.scalars(
                select(OrganizationMembership)
                .where(OrganizationMembership.user_id == user.id)
                .options(selectinload(OrganizationMembership.employee_profile))
            )
        ).all()
    )
    admin_accesses = list(
        (
            await db.scalars(
                select(AdminAccess).where(
                    AdminAccess.user_id == user.id,
                    AdminAccess.status == "active",
                )
            )
        ).all()
    )

    access_by_organization: dict[UUID, OrganizationAccess] = {}
    for membership in memberships:
        access_by_organization[membership.organization_id] = OrganizationAccess(
            organization_id=membership.organization_id,
            membership_status=cast(Literal["invited", "active", "suspended"], membership.status),
            is_employee=membership.employee_profile is not None,
            is_organization_admin=False,
        )
    platform_operator = False
    for access in admin_accesses:
        if access.scope == "platform_operator":
            platform_operator = True
            continue
        if access.organization_id is None:
            continue
        current = access_by_organization.get(access.organization_id)
        access_by_organization[access.organization_id] = OrganizationAccess(
            organization_id=access.organization_id,
            membership_status=current.membership_status if current else None,
            is_employee=current.is_employee if current else False,
            is_organization_admin=True,
        )

    return SessionResponse(
        user=SessionUser(
            id=user.id,
            email=user.email_normalized,
            preferred_locale=cast(Literal["uk", "en"], user.preferred_locale),
        ),
        session=SessionInfo(
            id=issued_session.id,
            absolute_expires_at=issued_session.absolute_expires_at,
            mfa_verified=issued_session.mfa_verified_at is not None,
        ),
        organization_access=list(access_by_organization.values()),
        platform_operator=platform_operator,
        csrf_token=derive_csrf_token(raw_token, hmac_key),
    )
