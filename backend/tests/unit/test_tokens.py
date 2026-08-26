from app.security.tokens import generate_opaque_token, hash_secret


def test_opaque_tokens_are_random_and_have_256_bits_of_entropy() -> None:
    first = generate_opaque_token()
    second = generate_opaque_token()

    assert first != second
    assert len(first) >= 43


def test_secret_hash_is_deterministic_without_containing_raw_value() -> None:
    raw = "raw-token-value"

    first = hash_secret(raw)
    second = hash_secret(raw)

    assert first == second
    assert len(first) == 64
    assert raw not in first
