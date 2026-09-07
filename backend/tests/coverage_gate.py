import argparse
import json
from pathlib import Path
from typing import cast

CRITICAL_FILES = frozenset(
    "app/" + name
    for name in (
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
)
COUNT_KEYS = (
    "covered_lines",
    "num_statements",
    "missing_lines",
    "covered_branches",
    "num_branches",
    "missing_branches",
)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Invalid report object")
    return cast(dict[str, object], value)


def _counts(value: object) -> dict[str, int]:
    raw = _mapping(value)
    result = {}
    for key in COUNT_KEYS:
        count = raw.get(key)
        if type(count) is not int or count < 0:
            raise ValueError("Invalid coverage count")
        result[key] = count
    if (
        result["covered_lines"] + result["missing_lines"] != result["num_statements"]
        or result["covered_branches"] + result["missing_branches"] != result["num_branches"]
    ):
        raise ValueError("Inconsistent coverage counts")
    return result


def check_report(report: object, *, app_root: Path) -> list[tuple[str, int, int, bool]]:
    data = _mapping(report)
    if _mapping(data.get("meta")).get("branch_coverage") is not True:
        raise ValueError("Branch coverage is required")
    files = _mapping(data.get("files"))
    expected = {"app/" + path.relative_to(app_root).as_posix() for path in app_root.rglob("*.py")}
    if not expected or not expected >= CRITICAL_FILES:
        raise ValueError("Required application sources are missing")
    normalized = {name.replace(chr(92), "/"): value for name, value in files.items()}
    if len(normalized) != len(files) or set(normalized) != expected:
        raise ValueError("Incomplete application source inventory")
    counts = {name: _counts(_mapping(value).get("summary")) for name, value in normalized.items()}
    totals = _counts(data.get("totals"))
    if any(totals[key] != sum(row[key] for row in counts.values()) for key in COUNT_KEYS):
        raise ValueError("Report totals do not match files")
    critical_covered = sum(
        counts[name]["covered_lines"] + counts[name]["covered_branches"] for name in CRITICAL_FILES
    )
    critical_total = sum(
        counts[name]["num_statements"] + counts[name]["num_branches"] for name in CRITICAL_FILES
    )
    metrics = [
        ("statements", totals["covered_lines"], totals["num_statements"]),
        ("branches", totals["covered_branches"], totals["num_branches"]),
        ("critical aggregate", critical_covered, critical_total),
    ]
    if any(total == 0 for _, _, total in metrics):
        raise ValueError("Coverage denominators must be nonzero")
    # Поріг перевіряється до округлення, щоб 79.99% не ставало успішним результатом.
    return [(name, covered, total, 100 * covered >= 80 * total) for name, covered, total in metrics]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check independent CRA-13 coverage gates")
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        results = check_report(report, app_root=Path("app"))
    except (OSError, ValueError):
        # Вміст звіту та локальні шляхи не потрапляють у повідомлення про помилку.
        print("Invalid or incomplete coverage report.")
        return 2
    for name, covered, total, passed in results:
        print(
            f"{name}: {covered}/{total} ({100 * covered / total:.2f}%) "
            f"{'PASS' if passed else 'FAIL'}"
        )
    return 0 if all(passed for _, _, _, passed in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
