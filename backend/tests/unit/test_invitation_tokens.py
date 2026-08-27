import pytest
from pydantic import SecretStr

from app.security.invitation_tokens import InvitationTokenManager
from app.security.tokens import hash_secret


def test_invitation_token_is_deterministic_and_versioned() -> None:
    manager = InvitationTokenManager([SecretStr("a" * 32), SecretStr("b" * 32)])
    invitation_id = "018f4f70-ec5d-7c99-a3f2-d4f447aaefe0"

    first = manager.derive(invitation_id, token_version=1, key_index=0)
    repeated = manager.derive(invitation_id, token_version=1, key_index=0)
    rotated = manager.derive(invitation_id, token_version=2, key_index=0)
    old_key = manager.derive(invitation_id, token_version=1, key_index=1)

    assert first == repeated
    assert first != rotated
    assert first != old_key
    assert len(hash_secret(first)) == 64


def test_current_key_is_the_first_ordered_key() -> None:
    manager = InvitationTokenManager([SecretStr("a" * 32), SecretStr("b" * 32)])

    assert manager.current_key_index == 0


def test_invitation_token_manager_rejects_missing_or_short_keys() -> None:
    with pytest.raises(ValueError, match="At least one"):
        InvitationTokenManager([])
    with pytest.raises(ValueError, match="32 characters"):
        InvitationTokenManager([SecretStr("short")])


def test_invitation_token_manager_rejects_unavailable_key_index() -> None:
    manager = InvitationTokenManager([SecretStr("a" * 32)])

    with pytest.raises(ValueError, match="unavailable"):
        manager.derive("invitation-id", token_version=1, key_index=1)
