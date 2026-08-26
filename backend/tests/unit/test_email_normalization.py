import pytest

from app.core.email import normalize_email


def test_normalize_email_trims_and_lowercases() -> None:
    assert normalize_email("  Employee@Example.COM  ") == "employee@example.com"


@pytest.mark.parametrize("value", ["", " ", "\t\r\n"])
def test_normalize_email_rejects_blank_value(value: str) -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_email(value)
