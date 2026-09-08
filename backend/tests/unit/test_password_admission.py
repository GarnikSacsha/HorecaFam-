import asyncio
import threading

import pytest

from app.core.errors import APIError
from app.security.passwords import PasswordManager


async def test_password_work_yields_and_rejects_excess_without_queueing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = PasswordManager()
    entered = threading.Event()
    release = threading.Event()

    def blocked(encoded: str | None, password: str) -> bool:
        entered.set()
        assert release.wait(5)
        return False

    monkeypatch.setattr(manager, "verify_or_dummy", blocked)
    tasks = []
    try:
        for _ in range(2):
            tasks.append(asyncio.create_task(manager.verify_or_dummy_async(None, "ordinary")))
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.01)
        assert entered.is_set()
        with pytest.raises(APIError, match="AUTH_RATE_LIMITED"):
            await manager.verify_or_dummy_async(None, "ordinary")
        tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await tasks[0]
        with pytest.raises(APIError, match="AUTH_RATE_LIMITED"):
            await manager.verify_or_dummy_async(None, "ordinary")
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(0.05)


async def test_password_async_preserves_hash_real_and_dummy_results() -> None:
    manager = PasswordManager()
    encoded = await manager.hash_async("ordinary-password")
    assert await manager.verify_async(encoded, "ordinary-password")
    assert not await manager.verify_async(encoded, "wrong-password")
    assert not await manager.verify_or_dummy_async(None, "ordinary-password")


async def test_oversized_password_rejected_before_crypto(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = PasswordManager()

    def forbidden(*args: object) -> bool:
        pytest.fail("Oversized password reached cryptographic work")

    monkeypatch.setattr(manager, "verify_or_dummy", forbidden)
    with pytest.raises(APIError, match="INVALID_CREDENTIALS"):
        await manager.verify_or_dummy_async(None, "x" * 1025)
