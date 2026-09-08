import asyncio
from collections.abc import Callable
from functools import partial
from threading import BoundedSemaphore
from typing import TypeVar

from argon2 import PasswordHasher, exceptions
from argon2.profiles import RFC_9106_LOW_MEMORY

from app.core.errors import APIError

_PASSWORD_SLOTS = BoundedSemaphore(2)
_Result = TypeVar("_Result")
MAX_PASSWORD_LENGTH = 1024


class PasswordManager:
    async def _run(self, operation: Callable[[], _Result], password: str) -> _Result:
        if len(password) > MAX_PASSWORD_LENGTH:
            raise APIError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="Неправильна електронна пошта або пароль.",
            )
        if not _PASSWORD_SLOTS.acquire(blocking=False):
            raise APIError(
                status_code=429,
                code="AUTH_RATE_LIMITED",
                message="Забагато спроб. Спробуйте пізніше.",
            )

        def execute() -> _Result:
            try:
                return operation()
            finally:
                # Скасований HTTP-запит не звільняє слот, поки Argon2 ще працює.
                _PASSWORD_SLOTS.release()

        try:
            future = asyncio.get_running_loop().run_in_executor(None, execute)
        except BaseException:
            _PASSWORD_SLOTS.release()
            raise
        return await asyncio.shield(future)

    async def hash_async(self, password: str) -> str:
        return await self._run(partial(self.hash, password), password)

    async def verify_async(self, encoded_hash: str, password: str) -> bool:
        return await self._run(partial(self.verify, encoded_hash, password), password)

    async def verify_or_dummy_async(self, encoded_hash: str | None, password: str) -> bool:
        return await self._run(partial(self.verify_or_dummy, encoded_hash, password), password)

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
