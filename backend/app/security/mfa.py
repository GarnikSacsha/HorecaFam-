import base64
import secrets
from collections.abc import Sequence
from datetime import datetime
from urllib.parse import quote

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP

TOTP_STEP_SECONDS = 30
RECOVERY_CODE_COUNT = 10


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


def generate_totp_secret() -> bytes:
    return secrets.token_bytes(20)


def encode_totp_secret(secret: bytes) -> str:
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def build_totp_uri(
    secret: bytes,
    *,
    account_name: str,
    issuer: str = "HoReCa Training",
) -> str:
    label = quote(f"{issuer}:{account_name}", safe="")
    encoded_issuer = quote(issuer, safe="")
    return (
        f"otpauth://totp/{label}?secret={encode_totp_secret(secret)}"
        f"&issuer={encoded_issuer}&algorithm=SHA1&digits=6&period={TOTP_STEP_SECONDS}"
    )


def normalize_recovery_code(code: str) -> str:
    return "".join(character for character in code.upper() if character.isalnum())


def generate_recovery_codes(*, count: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        compact = base64.b32encode(secrets.token_bytes(10)).decode("ascii").rstrip("=")
        codes.append("-".join(compact[index : index + 4] for index in range(0, 16, 4)))
    return codes
