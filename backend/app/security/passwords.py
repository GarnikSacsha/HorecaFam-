from argon2 import PasswordHasher, exceptions
from argon2.profiles import RFC_9106_LOW_MEMORY


class PasswordManager:
    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)
        self._dummy_hash = self._hasher.hash("horeca-dummy-password-value")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, encoded_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except (exceptions.VerificationError, exceptions.InvalidHashError):
            return False

    def verify_or_dummy(self, encoded_hash: str | None, password: str) -> bool:
        verified = self.verify(encoded_hash or self._dummy_hash, password)
        return verified if encoded_hash is not None else False

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except exceptions.InvalidHashError:
            return True
