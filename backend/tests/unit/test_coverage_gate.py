import copy
import json
from pathlib import Path

import pytest

from tests.coverage_gate import check_report, main

CRITICAL = (
    "services/password_recovery.py",
    "services/mfa_enrollment.py",
    "services/employees.py",
    "services/background_jobs.py",
    "services/background_job_handlers.py",
    "services/maintenance.py",
    "services/operator_jobs.py",
    "core/observability.py",
    "operations/bootstrap_venue.py",
)


def make_report(app_root: Path, statements: int = 80, branches: int = 80) -> dict[str, object]:
    files = {}
    for name in (*CRITICAL, "other.py"):
        path = app_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n", encoding="utf-8")
        files["app/" + name] = {
            "summary": {
                "covered_lines": statements,
                "num_statements": 100,
                "missing_lines": 100 - statements,
                "covered_branches": branches,
                "num_branches": 100,
                "missing_branches": 100 - branches,
            }
        }
    summary = {
        key: sum(value["summary"][key] for value in files.values())
        for key in next(iter(files.values()))["summary"]
    }
    return {"meta": {"branch_coverage": True}, "files": files, "totals": summary}


@pytest.mark.parametrize(
    ("statements", "branches", "expected"),
    [
        (80, 80, [True, True, True]),
        (100, 79, [True, False, True]),
        (79, 100, [False, True, True]),
        (79, 79, [False, False, False]),
    ],
)
def test_independent_gates(
    tmp_path: Path,
    statements: int,
    branches: int,
    expected: list[bool],
) -> None:
    app_root = tmp_path / "app"
    result = check_report(make_report(app_root, statements, branches), app_root=app_root)
    assert [row[3] for row in result] == expected
    assert [row[0] for row in result] == ["statements", "branches", "critical aggregate"]


def test_rounding_cannot_turn_a_failure_into_a_pass(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    report = make_report(app_root)
    files = report["files"]
    assert isinstance(files, dict)
    for entry in files.values():
        entry["summary"].update(num_branches=10000, covered_branches=7999, missing_branches=2001)
    totals = report["totals"]
    assert isinstance(totals, dict)
    totals.update(num_branches=100000, covered_branches=79990, missing_branches=20010)
    assert check_report(report, app_root=app_root)[1] == ("branches", 79990, 100000, False)


@pytest.mark.parametrize(
    "damage",
    [
        "branch_mode",
        "missing_source",
        "missing_critical",
        "bad_count",
        "negative",
        "inconsistent_totals",
        "empty",
        "missing_totals",
        "missing_branch_count",
    ],
)
def test_invalid_or_incomplete_reports_fail_closed(tmp_path: Path, damage: str) -> None:
    app_root = tmp_path / "app"
    report = make_report(app_root)
    files = report["files"]
    totals = report["totals"]
    assert isinstance(files, dict) and isinstance(totals, dict)
    if damage == "branch_mode":
        report["meta"] = {"branch_coverage": False}
    elif damage == "missing_source":
        del files["app/other.py"]
    elif damage == "missing_critical":
        (app_root / CRITICAL[0]).unlink()
        del files["app/" + CRITICAL[0]]
    elif damage == "bad_count":
        totals["covered_lines"] = True
    elif damage == "negative":
        files["app/other.py"]["summary"]["covered_lines"] = -1
    elif damage == "inconsistent_totals":
        totals["covered_lines"] = 999
    elif damage == "empty":
        report["files"] = {}
    elif damage == "missing_totals":
        del report["totals"]
    else:
        del files["app/other.py"]["summary"]["num_branches"]
    with pytest.raises(ValueError):
        check_report(report, app_root=app_root)


def test_cli_returns_failure_for_invalid_json_without_printing_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "report.json"
    path.write_text("private-invalid-payload", encoding="utf-8")
    assert main([str(path)]) == 2
    assert "private-invalid-payload" not in capsys.readouterr().out


def test_cli_counts_and_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    app_root = tmp_path / "app"
    report = make_report(app_root, 100, 79)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert main([str(path)]) == 1
    output = capsys.readouterr().out
    assert "branches: 790/1000" in output and "FAIL" in output
    good = copy.deepcopy(make_report(app_root, 80, 80))
    path.write_text(json.dumps(good), encoding="utf-8")
    assert main([str(path)]) == 0
