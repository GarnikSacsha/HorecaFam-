import argparse
import getpass
import sys
import warnings

import pytest

from app.operations import provision_access as provisioning


def test_password_requires_private_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(provisioning.ProvisioningError):
        provisioning.read_password()


@pytest.mark.parametrize("values", [("short", "short"), ("long-password", "different-password")])
def test_password_confirmation_rejects_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
    values: tuple[str, str],
) -> None:
    inputs = iter(values)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(getpass, "getpass", lambda _: next(inputs))
    with pytest.raises(provisioning.ProvisioningError):
        provisioning.read_password()


def test_visible_getpass_fallback_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    def unsafe_prompt(_: str) -> str:
        warnings.warn("Echo would be enabled", getpass.GetPassWarning, stacklevel=2)
        pytest.fail("Visible input must not be reached")

    monkeypatch.setattr(getpass, "getpass", unsafe_prompt)
    with pytest.raises(getpass.GetPassWarning):
        provisioning.read_password()


def test_cli_suppresses_exception_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fail(_: argparse.Namespace) -> provisioning.ProvisionResult:
        raise RuntimeError("synthetic-sensitive-payload")

    monkeypatch.setattr(provisioning, "run", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "provision_access",
            "initial-operator",
            "--email",
            "operator@example.com",
            "--confirm-environment",
            "test",
            "--expected-host",
            "localhost",
            "--expected-database",
            "horeca_test",
            "--expected-db-user",
            "test",
        ],
    )
    with pytest.raises(SystemExit) as error:
        provisioning.main()
    assert error.value.code == 1
    output = capsys.readouterr()
    assert "synthetic-sensitive-payload" not in output.err + output.out
    assert "inspect target and account state" in output.err
