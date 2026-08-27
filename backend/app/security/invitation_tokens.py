import base64
import hashlib
import hmac
from uuid import UUID

from pydantic import SecretStr


class InvitationTokenManager:
    def __init__(self, ordered_keys: list[SecretStr]) -> None:
        if not ordered_keys:
            raise ValueError("At least one Invitation token key is required")
        if any(len(key.get_secret_value()) < 32 for key in ordered_keys):
            raise ValueError("Every Invitation token key must contain at least 32 characters")
        self._keys = tuple(key.get_secret_value().encode("utf-8") for key in ordered_keys)

    @property
    def current_key_index(self) -> int:
        return 0

    def derive(
        self,
        invitation_id: UUID | str,
        *,
        token_version: int,
        key_index: int,
    ) -> str:
        if token_version < 1:
            raise ValueError("Invitation token version must be positive")
        try:
            key = self._keys[key_index]
        except IndexError as exception:
            raise ValueError("Invitation token key index is unavailable") from exception
        if key_index < 0:
            raise ValueError("Invitation token key index is unavailable")
        message = f"horeca-invitation:v1:{invitation_id}:{token_version}".encode()
        digest = hmac.new(key, message, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
