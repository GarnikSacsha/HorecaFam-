from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.session import (
    AuthenticatedSession,
    get_csrf_protected_session,
    get_current_session,
)
from app.core.clock import Clock
from app.core.config import Settings
from app.core.cookies import set_mfa_challenge_cookie, set_session_cookie
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.auth import (
    LoginRequest,
    MfaRequiredResponse,
    MfaVerifyRequest,
    PasswordChangeRequest,
    PasswordForgotRequest,
    PasswordForgotResponse,
    PasswordResetRequest,
    SessionResponse,
)
from app.security.passwords import PasswordManager
from app.services.auth import login, verify_mfa
from app.services.password_recovery import (
    change_password,
    request_password_reset,
    reset_password,
)
from app.services.sessions import build_session_response, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/password/forgot",
    response_model=PasswordForgotResponse,
    status_code=202,
)
async def password_forgot_route(
    payload: PasswordForgotRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasswordForgotResponse:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    await request_password_reset(
        db,
        email=str(payload.email),
        settings=settings,
        now=clock(),
        request_id=UUID(get_request_id()),
    )
    return PasswordForgotResponse()


@router.post("/password/reset", status_code=204)
async def password_reset_route(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    passwords = cast(PasswordManager, request.app.state.password_manager)
    await reset_password(
        db,
        raw_token=payload.token.get_secret_value(),
        new_password=payload.new_password.get_secret_value(),
        settings=settings,
        passwords=passwords,
        now=clock(),
        request_id=UUID(get_request_id()),
    )
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/api/v1",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


@router.post("/password/change", status_code=204)
async def password_change_route(
    payload: PasswordChangeRequest,
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    clock = cast(Clock, request.app.state.clock)
    passwords = cast(PasswordManager, request.app.state.password_manager)
    await change_password(
        db,
        current_session=current.record,
        user=current.user,
        current_password=payload.current_password.get_secret_value(),
        new_password=payload.new_password.get_secret_value(),
        passwords=passwords,
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post("/login", response_model=SessionResponse | MfaRequiredResponse)
async def login_route(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse | MfaRequiredResponse:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    passwords = cast(PasswordManager, request.app.state.password_manager)
    now = clock()
    outcome = await login(
        db,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        settings=settings,
        passwords=passwords,
        now=now,
        request_id=UUID(get_request_id()),
        user_agent=request.headers.get("user-agent"),
    )
    if outcome.kind == "mfa_required":
        if outcome.challenge_token is None or outcome.challenge_expires_at is None:
            raise RuntimeError("MFA challenge outcome is incomplete")
        response.status_code = 202
        set_mfa_challenge_cookie(
            response,
            settings,
            outcome.challenge_token,
            outcome.challenge_expires_at,
            now,
        )
        return MfaRequiredResponse(expires_at=outcome.challenge_expires_at)

    if outcome.session is None:
        raise RuntimeError("Session login outcome is incomplete")
    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    set_session_cookie(
        response,
        settings,
        outcome.session.raw_token,
        outcome.session.record.absolute_expires_at,
        now,
    )
    return await build_session_response(
        db,
        issued_session=outcome.session.record,
        user=outcome.user,
        raw_token=outcome.session.raw_token,
        hmac_key=hmac_key,
    )


@router.post("/logout", status_code=204)
async def logout_route(
    request: Request,
    response: Response,
    current: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    clock = cast(Clock, request.app.state.clock)
    await revoke_session(
        db,
        session=current.record,
        now=clock(),
        request_id=UUID(get_request_id()),
    )
    settings = cast(Settings, request.app.state.settings)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/api/v1",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


@router.post("/mfa/verify", response_model=SessionResponse)
async def verify_mfa_route(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    now = clock()
    outcome = await verify_mfa(
        db,
        raw_challenge=request.cookies.get(settings.mfa_challenge_cookie_name),
        code=payload.code,
        settings=settings,
        now=now,
        request_id=UUID(get_request_id()),
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(
        response,
        settings,
        outcome.session.raw_token,
        outcome.session.record.absolute_expires_at,
        now,
    )
    response.delete_cookie(
        key=settings.mfa_challenge_cookie_name,
        path="/api/v1",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )
    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    return await build_session_response(
        db,
        issued_session=outcome.session.record,
        user=outcome.user,
        raw_token=outcome.session.raw_token,
        hmac_key=hmac_key,
    )


@router.get("/session", response_model=SessionResponse)
async def session_context(
    request: Request,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    settings = cast(Settings, request.app.state.settings)
    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    response = await build_session_response(
        db,
        issued_session=current.record,
        user=current.user,
        raw_token=current.raw_token,
        hmac_key=hmac_key,
    )
    await db.commit()
    return response
