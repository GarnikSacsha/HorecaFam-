# HoReCa Testing and Quality Commands

This file owns supported test boundaries, commands and gates. Current results live in
[the testing index](../docs/testing/README.md) and [STATUS](../STATUS.md).
[Historical harness snapshots](../docs/history/harness-checkpoints-through-2026-09-15.md)
are evidence, not commands to repeat.

## Supported baseline

- Python: 3.12 only, as constrained by `backend/pyproject.toml`.
- Database: real PostgreSQL 16 for integration and migration tests.
- Local boundaries: `compose.test.yml` or native PostgreSQL 16.
- SQLite fallback: prohibited.
- Test environment: `APP_ENV=test` and a dedicated database named `horeca_test` or an approved
  worker-scoped derivative.

## Independent coverage gates

Overall statement coverage and overall branch coverage must each be at least 80%.
The fixed critical aggregate must be at least 80%; preserve its accepted file set.
Use `tests.coverage_gate` for raw-count and complete source-inventory validation.
Combined coverage alone cannot satisfy separate statement and branch gates.
Coverage uses the configured `greenlet` tracer for SQLAlchemy async execution.

## Environment setup

Run from the repository root:

```powershell
rtk py -3.12 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
```

Docker Compose remains a supported boundary when Docker is available:

```powershell
rtk docker compose -f compose.test.yml up -d --wait
```

The accepted local fallback is native PostgreSQL 16. Store native or Compose test values only in
the ignored `backend/.env.test`; never paste its values into documentation, Linear, logs, or Git.
The file uses these keys with local values:

```dotenv
APP_ENV=test
TEST_DATABASE_URL=<local-test-postgresql-async-url>
DATABASE_URL=<same-local-test-postgresql-async-url>
```

Before a PostgreSQL gate, load the ignored file into the current PowerShell process without
printing it:

```powershell
$testEnvPath = Resolve-Path .env.test
foreach ($line in [IO.File]::ReadAllLines($testEnvPath)) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { continue }
    $parts = $line.Split(@("="), 2, [StringSplitOptions]::None)
    if ($parts.Count -ne 2) { throw "Invalid .env.test entry." }
    [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
}
if ($env:APP_ENV -ne "test") { throw "APP_ENV=test is required." }
if ($env:TEST_DATABASE_URL -notmatch "/horeca_test(?:_[a-z0-9]+)*$") {
    throw "A dedicated horeca_test database is required."
}
```

Run this snippet from `backend/`. Do not echo the resulting variables.

## Exact project commands

After a successful fresh full coverage run, generate and evaluate the report from `backend/`.
The report must come from that same successful run; do not reuse an old JSON after an error.
Keep generated evidence in the ignored test cache and out of Git:

```powershell
rtk ..\.venv\Scripts\python.exe -m coverage json -o .pytest_cache/cra125/current.json
rtk ..\.venv\Scripts\python.exe -m tests.coverage_gate .pytest_cache/cra125/current.json
```

Exit codes: 0 means all three gates pass; 1 means a threshold fails; 2 means report validation
failed. Combined `--cov-fail-under` alone cannot enforce the two independent overall gates.

Run from `backend/`:

```powershell
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini current --check-heads
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Example targeted commands:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_health.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_database.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_identity_models.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/migration/test_migrations.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_auth_login.py tests/api/test_auth_session.py tests/api/test_auth_csrf_logout.py tests/api/test_auth_mfa_rbac.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_invitations_create_validate.py tests/api/test_invitations_resend_revoke.py tests/integration/test_invitation_services.py -vv -p no:cacheprovider
```

The full gate is not green when required PostgreSQL tests are skipped. Report passed, failed, and
skipped counts explicitly.

## Frontend commands

Use Node.js 24 and pnpm 11. Run from `frontend/`:

```powershell
rtk pnpm install --frozen-lockfile
rtk pnpm format:check
rtk pnpm lint
rtk pnpm typecheck
rtk pnpm test
rtk pnpm build
rtk pnpm exec playwright install chromium
rtk pnpm test:e2e
```

## Evidence discipline

- Run the smallest relevant suite and proportionate adjacent checks for the actual changed source.
- Record passed, failed and skipped counts; filtered RED cases are not a complete acceptance gate.
- Report setup failures and timeouts separately. A passing isolated retry does not erase a failed
  combined run. Do not weaken assertions or increase limits merely to obtain GREEN.
- Browser mock API checks do not prove authenticated staging, real email, storage or data writes.
- Dependencies and browser installation commands below the environment setup boundary require
  the existing project authorization; do not reinstall an already working environment for routine checks.
- Full coverage must come from the same successful full run; never reuse an old report after errors.
