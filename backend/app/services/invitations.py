import hashlib
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.email import normalize_email
from app.core.errors import APIError
from app.models import (
    AuditEvent,
    Invitation,
    InvitationRateLimitBucket,
    Organization,
    OrganizationMembership,
    User,
)
from app.schemas.invitations import InvitationResponse, InvitationValidationResponse
from app.security.invitation_tokens import InvitationTokenManager
from app.security.tokens import hash_secret
from app.services.idempotency import request_fingerprint, reserve_idempotency
from app.services.invitation_delivery import enqueue_invitation_email

INVITATION_LIFETIME = timedelta(hours=72)
INVITATION_RATE_WINDOW = timedelta(minutes=15)
INVITATION_RATE_BLOCK = timedelta(minutes=15)
CREATE_RATE_LIMIT = 10
VALIDATE_FAILURE_LIMIT = 10


def _rate_limited() -> APIError:
    return APIError(
        status_code=429,
        code="AUTH_RATE_LIMITED",
        message="Забагато спроб. Спробуйте пізніше.",
    )


def _subject_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _advisory_key(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big", signed=True)


async def _lock_subject(db: AsyncSession, value: str) -> None:
    await db.execute(select(func.pg_advisory_xact_lock(_advisory_key(value))))


async def consume_invitation_rate_limit(
    db: AsyncSession,
    *,
    action: str,
    subject_hash: str,
    limit: int,
    now: datetime,
) -> None:
    await _lock_subject(db, f"invitation-rate:{action}:{subject_hash}")
    bucket = await db.scalar(
        select(InvitationRateLimitBucket)
        .where(
            InvitationRateLimitBucket.action == action,
            InvitationRateLimitBucket.subject_hash == subject_hash,
        )
        .with_for_update()
    )
    if bucket is None:
        bucket = InvitationRateLimitBucket(
            action=action,
            subject_hash=subject_hash,
            window_started_at=now,
            request_count=1,
        )
        db.add(bucket)
    elif bucket.blocked_until is not None and bucket.blocked_until > now:
        await db.commit()
        raise _rate_limited()
    elif now - bucket.window_started_at >= INVITATION_RATE_WINDOW:
        bucket.window_started_at = now
        bucket.request_count = 1
        bucket.blocked_until = None
    else:
        bucket.request_count += 1

    blocked = bucket.request_count > limit
    if blocked:
        bucket.blocked_until = now + INVITATION_RATE_BLOCK
    await db.commit()
    if blocked:
        raise _rate_limited()


def invitation_response(invitation: Invitation, *, now: datetime) -> InvitationResponse:
    status = (
        "expired"
        if invitation.status == "pending" and invitation.expires_at <= now
        else invitation.status
    )
    return InvitationResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email_normalized,
        status=status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
    )


async def _membership_conflict(
    db: AsyncSession,
    *,
    organization_id: UUID,
    email_normalized: str,
) -> None:
    membership_status = await db.scalar(
        select(OrganizationMembership.status)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            User.email_normalized == email_normalized,
        )
    )
    conflicts = {
        "active": ("MEMBERSHIP_ALREADY_ACTIVE", "Користувач уже має активний доступ."),
        "pending": ("MEMBERSHIP_ALREADY_PENDING", "Доступ користувача вже очікує активації."),
        "disabled": ("MEMBERSHIP_DISABLED", "Доступ користувача вимкнено."),
    }
    if membership_status in conflicts:
        code, message = conflicts[membership_status]
        raise APIError(status_code=409, code=code, message=message)


async def create_invitation(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    email: str,
    idempotency_key: str,
    settings: Settings,
    now: datetime,
    request_id: UUID,
) -> Invitation:
    settings.validate_invitation_security()
    await consume_invitation_rate_limit(
        db,
        action="create",
        subject_hash=_subject_hash(f"{actor_user_id}:{organization_id}"),
        limit=CREATE_RATE_LIMIT,
        now=now,
    )
    email_normalized = normalize_email(email)
    candidate_id = uuid4()
    decision = await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="invitation.create",
        key=idempotency_key,
        fingerprint=request_fingerprint({"email": email_normalized}),
        resource_type="invitation",
        resource_id=candidate_id,
        response_status=201,
        now=now,
    )
    if decision.replayed:
        invitation = await db.scalar(
            select(Invitation).where(
                Invitation.id == decision.record.resource_id,
                Invitation.organization_id == organization_id,
            )
        )
        if invitation is None:
            raise RuntimeError("Idempotent Invitation resource is unavailable")
        await db.commit()
        return invitation

    await _lock_subject(db, f"invitation-email:{organization_id}:{email_normalized}")
    await _membership_conflict(
        db,
        organization_id=organization_id,
        email_normalized=email_normalized,
    )
    pending = await db.scalar(
        select(Invitation.id).where(
            Invitation.organization_id == organization_id,
            Invitation.email_normalized == email_normalized,
            Invitation.status == "pending",
        )
    )
    if pending is not None:
        raise APIError(
            status_code=409,
            code="INVITATION_ALREADY_PENDING",
            message="Запрошення для цієї адреси вже очікує дії.",
        )

    token_manager = InvitationTokenManager(settings.invitation_token_hmac_keys)
    raw_token = token_manager.derive(candidate_id, token_version=1, key_index=0)
    invitation = Invitation(
        id=candidate_id,
        organization_id=organization_id,
        email_normalized=email_normalized,
        token_hash=hash_secret(raw_token),
        token_version=1,
        token_key_index=token_manager.current_key_index,
        status="pending",
        invited_by_user_id=actor_user_id,
        expires_at=now + INVITATION_LIFETIME,
    )
    db.add(invitation)
    await db.flush()
    await enqueue_invitation_email(db, invitation=invitation)
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="invitation_created",
            target_type="invitation",
            target_id=invitation.id,
            request_id=request_id,
            outcome="success",
            new_values={
                "status": "pending",
                "expires_at": invitation.expires_at.isoformat(),
                "token_version": invitation.token_version,
            },
        )
    )
    await db.commit()
    return invitation


def _invitation_not_found() -> APIError:
    return APIError(
        status_code=404,
        code="INVITATION_NOT_FOUND",
        message="Запрошення не знайдено.",
    )


def _mask_email(email: str) -> str:
    local, domain = email.split("@", maxsplit=1)
    return f"{local[:1]}***@{domain}"


async def _failed_validation(
    db: AsyncSession,
    *,
    subject_hash: str,
    now: datetime,
    error: APIError,
) -> None:
    await consume_invitation_rate_limit(
        db,
        action="validate",
        subject_hash=subject_hash,
        limit=VALIDATE_FAILURE_LIMIT,
        now=now,
    )
    raise error


async def validate_invitation(
    db: AsyncSession,
    *,
    raw_token: str,
    now: datetime,
) -> InvitationValidationResponse:
    token_hash = hash_secret(raw_token)
    row = (
        await db.execute(
            select(Invitation, Organization)
            .join(Organization, Organization.id == Invitation.organization_id)
            .where(Invitation.token_hash == token_hash)
        )
    ).one_or_none()
    if row is None:
        await _failed_validation(
            db,
            subject_hash=token_hash,
            now=now,
            error=_invitation_not_found(),
        )
        raise RuntimeError("Failed validation returned unexpectedly")
    invitation, organization = row
    if invitation.status == "revoked":
        await _failed_validation(
            db,
            subject_hash=token_hash,
            now=now,
            error=APIError(
                status_code=410,
                code="INVITATION_REVOKED",
                message="Запрошення відкликано.",
            ),
        )
    if invitation.status == "accepted":
        await _failed_validation(
            db,
            subject_hash=token_hash,
            now=now,
            error=APIError(
                status_code=409,
                code="INVITATION_ALREADY_ACCEPTED",
                message="Запрошення вже використано.",
            ),
        )
    if invitation.expires_at <= now:
        await _failed_validation(
            db,
            subject_hash=token_hash,
            now=now,
            error=APIError(
                status_code=410,
                code="INVITATION_EXPIRED",
                message="Строк дії запрошення минув.",
            ),
        )

    bucket = await db.scalar(
        select(InvitationRateLimitBucket).where(
            InvitationRateLimitBucket.action == "validate",
            InvitationRateLimitBucket.subject_hash == token_hash,
        )
    )
    if bucket is not None:
        await db.delete(bucket)
    user_exists = (
        await db.scalar(select(User.id).where(User.email_normalized == invitation.email_normalized))
        is not None
    )
    await db.commit()
    return InvitationValidationResponse(
        organization_id=organization.id,
        organization_name=organization.name,
        email_masked=_mask_email(invitation.email_normalized),
        acceptance_mode="accept_existing_account" if user_exists else "activate_access",
        expires_at=invitation.expires_at,
    )
