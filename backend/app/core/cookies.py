from datetime import datetime

from fastapi import Response

from app.core.config import Settings


def set_session_cookie(
    response: Response,
    settings: Settings,
    raw_token: str,
    expires_at: datetime,
    now: datetime,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=max(0, int((expires_at - now).total_seconds())),
        path="/api/v1",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def set_mfa_challenge_cookie(
    response: Response,
    settings: Settings,
    raw_token: str,
    expires_at: datetime,
    now: datetime,
) -> None:
    response.set_cookie(
        key=settings.mfa_challenge_cookie_name,
        value=raw_token,
        max_age=max(0, int((expires_at - now).total_seconds())),
        path="/api/v1",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def clear_mfa_challenge_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.mfa_challenge_cookie_name,
        path="/api/v1",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )
