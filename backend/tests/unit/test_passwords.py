from argon2 import PasswordHasher
from argon2.low_level import Type

from app.security.passwords import PasswordManager


def test_password_manager_hashes_and_verifies_argon2id() -> None:
    manager = PasswordManager()

    encoded = manager.hash("correct horse battery staple")

    assert encoded.startswith("$argon2id$")
    assert manager.verify(encoded, "correct horse battery staple") is True
    assert manager.verify(encoded, "wrong password") is False


def test_password_manager_rejects_invalid_encoded_hash() -> None:
    manager = PasswordManager()

    assert manager.verify("not-an-argon2-hash", "password") is False


def test_password_manager_detects_hash_that_needs_rehash() -> None:
    legacy_hasher = PasswordHasher(
        time_cost=1,
        memory_cost=8,
        parallelism=1,
        hash_len=16,
        salt_len=16,
        type=Type.ID,
    )
    manager = PasswordManager()

    assert manager.needs_rehash(legacy_hasher.hash("password")) is True


def test_unknown_user_uses_dummy_hash_without_authenticating() -> None:
    manager = PasswordManager()

    assert manager.verify_or_dummy(None, "password") is False
