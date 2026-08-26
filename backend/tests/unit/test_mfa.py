from datetime import UTC, datetime

from cryptography.fernet import Fernet

from app.security.mfa import MfaSecretCipher, TotpVerifier


def test_mfa_secret_cipher_encrypts_and_decrypts_with_rotatable_keys() -> None:
    primary = Fernet.generate_key().decode()
    previous = Fernet.generate_key().decode()
    cipher = MfaSecretCipher([primary, previous])

    encrypted = cipher.encrypt(b"01234567890123456789")

    assert encrypted != "01234567890123456789"
    assert cipher.decrypt(encrypted) == b"01234567890123456789"


def test_totp_verifier_accepts_current_window_and_rejects_replay() -> None:
    verifier = TotpVerifier()
    secret = b"01234567890123456789"
    current = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    code = verifier.generate(secret, current)

    counter = verifier.verify(secret, code, current, last_used_counter=None)

    assert counter is not None
    assert verifier.verify(secret, code, current, last_used_counter=counter) is None


def test_totp_verifier_accepts_adjacent_clock_step() -> None:
    verifier = TotpVerifier()
    secret = b"01234567890123456789"
    generated_at = datetime(2026, 8, 26, 11, 59, 30, tzinfo=UTC)
    verified_at = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)

    code = verifier.generate(secret, generated_at)

    assert verifier.verify(secret, code, verified_at, last_used_counter=None) is not None


def test_totp_verifier_rejects_invalid_code() -> None:
    verifier = TotpVerifier()
    secret = b"01234567890123456789"

    assert (
        verifier.verify(
            secret,
            "000000",
            datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
            last_used_counter=None,
        )
        is None
    )
