from collections.abc import Sequence
from datetime import datetime

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP

TOTP_STEP_SECONDS = 30


class MfaSecretCipher:
    def __init__(self, keys: Sequence[str]) -> None:
        if not keys:
            raise ValueError("At least one MFA encryption key is required")
        self._cipher = MultiFernet([Fernet(key.encode("ascii")) for key in keys])

    def encrypt(self, secret: bytes) -> str:
        return self._cipher.encrypt(secret).decode("ascii")

    def decrypt(self, encrypted_secret: str) -> bytes:
        return self._cipher.decrypt(encrypted_secret.encode("ascii"))


class TotpVerifier:
    def _totp(self, secret: bytes) -> TOTP:
        return TOTP(secret, 6, SHA1(), TOTP_STEP_SECONDS)

    def generate(self, secret: bytes, at: datetime) -> str:
        return self._totp(secret).generate(at.timestamp()).decode("ascii")

    def verify(
        self,
        secret: bytes,
        code: str,
        at: datetime,
        *,
        last_used_counter: int | None,
    ) -> int | None:
        if len(code) != 6 or not code.isascii() or not code.isdigit():
            return None

        current_counter = int(at.timestamp()) // TOTP_STEP_SECONDS
        for counter in range(current_counter - 1, current_counter + 2):
            if last_used_counter is not None and counter <= last_used_counter:
                continue
            try:
                self._totp(secret).verify(code.encode("ascii"), counter * TOTP_STEP_SECONDS)
            except InvalidToken:
                continue
            return counter
        return None
