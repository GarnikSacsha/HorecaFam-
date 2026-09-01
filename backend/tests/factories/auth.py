from datetime import UTC, datetime, timedelta
from typing import Any

from app.models import (
    AdminAccess,
    MfaChallenge,
    MfaCredential,
    MfaRecoveryCode,
    PasswordResetToken,
    Session,
    User,
)


def make_admin_access(user: User, **overrides: Any) -> AdminAccess:
    values: dict[str, Any] = {
        "user_id": user.id,
        "scope": "platform_operator",
        "status": "active",
        "granted_at": datetime.now(UTC),
    }
    values.update(overrides)
    return AdminAccess(**values)


def make_session(user: User, **overrides: Any) -> Session:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "user_id": user.id,
        "token_hash": "a" * 64,
        "csrf_token_hash": "b" * 64,
        "last_seen_at": now,
        "absolute_expires_at": now + timedelta(days=90),
    }
    values.update(overrides)
    return Session(**values)


def make_mfa_credential(user: User, **overrides: Any) -> MfaCredential:
    values: dict[str, Any] = {
        "user_id": user.id,
        "type": "totp",
        "secret_encrypted": "encrypted-test-secret",
        "confirmed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return MfaCredential(**values)


def make_mfa_recovery_code(credential: MfaCredential, **overrides: Any) -> MfaRecoveryCode:
    values: dict[str, Any] = {
        "mfa_credential_id": credential.id,
        "code_hash": "d" * 64,
    }
    values.update(overrides)
    return MfaRecoveryCode(**values)


def make_mfa_challenge(user: User, **overrides: Any) -> MfaChallenge:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "user_id": user.id,
        "token_hash": "c" * 64,
        "expires_at": now + timedelta(minutes=5),
    }
    values.update(overrides)
    return MfaChallenge(**values)


def make_password_reset_token(user: User, **overrides: Any) -> PasswordResetToken:
    values: dict[str, Any] = {
        "user_id": user.id,
        "token_hash": "r" * 64,
        "expires_at": datetime.now(UTC) + timedelta(minutes=30),
    }
    values.update(overrides)
    return PasswordResetToken(**values)
