# HoReCa Testing and Quality Commands

## Supported baseline

- Python: 3.12 only, as constrained by `backend/pyproject.toml`.
- Database: real PostgreSQL 16 for integration and migration tests.
- Local boundaries: `compose.test.yml` or native PostgreSQL 16.
- SQLite fallback: prohibited.
- Test environment: `APP_ENV=test` and a dedicated database named `horeca_test` or an approved
  worker-scoped derivative.

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

## Accepted Stage 0 evidence

CRA-20 was accepted on 2026-08-26 with Python 3.12.10 and native PostgreSQL 16.15:

- 22 passed, 0 failed, 0 skipped;
- 95% Stage 0 statement/branch coverage;
- live async SQLAlchemy/asyncpg round-trip;
- fresh database upgraded to Alembic head `0001_stage0`;
- Ruff format, Ruff check, and mypy passed.

This is historical accepted evidence, not a substitute for rerunning checks after behavior changes.
See [`../docs/testing/README.md`](../docs/testing/README.md) and the canonical CRA-20 evidence in
Linear.

## Accepted Stage 1 evidence

CRA-28 was accepted with a local Python 3.12.10/PostgreSQL 16.15 gate reporting 47 passed,
0 failed, 0 skipped, 97% coverage, Alembic head
`0002_identity_persistence`, and no metadata drift. Rerun the complete gate before relying on this
snapshot or preparing any authorized commit.

## Accepted CRA-30 Stage 2 evidence

The accepted CRA-30 checkpoint uses the same Python 3.12.10 and native PostgreSQL 16.15 boundary.
Its final complete gate reports 92 passed, 0 failed, 0 skipped, 94% overall statement/branch
coverage, 92% critical auth coverage, Alembic head `0003_auth_security`, and no metadata drift.
Canonical evidence remains in Linear.

## Accepted CRA-32 Stage 3 evidence

The accepted CRA-32 invitation checkpoint uses Python 3.12.10 and native PostgreSQL 16.15. Its
complete gate reports 156 passed, 0 failed, 0 skipped, 94% overall statement/branch coverage, 90%
aggregate critical invitation coverage, Alembic head `0005_invitation_email_outbox`, and no
metadata drift. Canonical evidence remains in Linear.

## Accepted CRA-34 Stage 4 evidence

The accepted invitation-acceptance checkpoint uses the same Python 3.12.10 and native PostgreSQL 16.15
boundary. Its final gate reports 180 passed, 0 failed, 0 skipped, 94% overall statement/branch
coverage, 93% aggregate critical acceptance coverage, Alembic head
`0005_invitation_email_outbox`, and no metadata drift. Focused API acceptance reports 12 passed.
CRA-34 is Done and its four commits are published through `9fd2130`. Canonical evidence remains in
Linear.

## Accepted CRA-36 Stage 5 evidence

The accepted Pending/Admin Profile Setup checkpoint uses Python 3.12.10 and native PostgreSQL 16.
Its complete gate reports 195 passed, 0 failed, 0 skipped, 94% overall branch coverage, and 92%
aggregate critical Stage 5 coverage. Focused Stage 5 API/integration reports 15 passed. Alembic
remains at `0005_invitation_email_outbox`; the empty-database migration test, current head check,
and metadata no-drift check pass. Canonical acceptance and publication evidence remains in Linear.

Coverage enables the standard `greenlet` concurrency tracer because SQLAlchemy's async adapter
crosses greenlet contexts. Without it, executed post-database branches are under-reported.
