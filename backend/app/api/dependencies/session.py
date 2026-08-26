import secrets
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import APIError
from app.db.dependencies import get_db
from app.models import Session, User
from app.security.tokens import hash_secret
from app.services.sessions import SESSION_INACTIVITY


@dataclass(frozen=True)
class AuthenticatedSession:
    record: Session
    user: User
    raw_token: str


async def get_current_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthenticatedSession:
    settings = cast(Settings, request.app.state.settings)
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is None:
        raise APIError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="Потрібна автентифікація.",
        )
    record = await db.scalar(
        select(Session)
        .where(Session.token_hash == hash_secret(raw_token))
        .options(selectinload(Session.user))
    )
    clock = cast(Clock, request.app.state.clock)
    now = clock()
    if (
        record is None
        or record.revoked_at is not None
        or record.absolute_expires_at <= now
        or record.last_seen_at + SESSION_INACTIVITY <= now
    ):
        raise APIError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="Потрібна автентифікація.",
        )
    record.last_seen_at = now
    return AuthenticatedSession(record=record, user=record.user, raw_token=raw_token)


def _csrf_error() -> APIError:
    return APIError(
        status_code=403,
        code="CSRF_INVALID",
        message="CSRF-перевірка не пройдена.",
    )


async def get_csrf_protected_session(
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
) -> AuthenticatedSession:
    settings = cast(Settings, request.app.state.settings)
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_allowed_origins:
        raise _csrf_error()

    csrf_token = request.headers.get("x-csrf-token")
    if csrf_token is None or not secrets.compare_digest(
        hash_secret(csrf_token), current.record.csrf_token_hash
    ):
        raise _csrf_error()
    return current
