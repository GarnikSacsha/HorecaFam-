# HoReCa Testing and Quality Commands

## Supported baseline

- Python: 3.12 only, as constrained by `backend/pyproject.toml`.
- Database: real PostgreSQL 16 for integration and migration tests.
- Local boundaries: `compose.test.yml` or native PostgreSQL 16.
- SQLite fallback: prohibited.
- Test environment: `APP_ENV=test` and a dedicated database named `horeca_test` or an approved
  worker-scoped derivative.

The published repository includes the accepted CRA-48 corrective record after `3b95b3c`.
CRA-43 runtime acceptance evidence remains anchored to its implementation endpoint `fa30a1f`.
CRA-47 planning and CRA-48 documentation are Done. CRA-49 is accepted and fast-forward published
through corrective checkpoint `8028d6e`; its evidence is recorded in
[`../docs/testing/menu-slice-2-acceptance.md`](../docs/testing/menu-slice-2-acceptance.md).
CRA-53 planning and CRA-54 implementation are accepted and Done. CRA-54 is published through
`d955f6a`; its evidence is recorded in
[`../docs/testing/training-slice-3-acceptance.md`](../docs/testing/training-slice-3-acceptance.md).
CRA-55 documentation synchronization and CRA-56 Slice 4 planning are Done. CRA-57 is accepted,
Done, and fast-forward published through `d4e0184`; its evidence is recorded in
[`../docs/testing/training-assignment-slice-4-acceptance.md`](../docs/testing/training-assignment-slice-4-acceptance.md).
CRA-60 planning is accepted and Done. CRA-61 is a local Interactive Training acceptance candidate;
its evidence is recorded in
[`../docs/testing/interactive-training-slice-5-acceptance.md`](../docs/testing/interactive-training-slice-5-acceptance.md).

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

## Accepted CRA-38 Stage 6 evidence

The Explicit Activation candidate uses Python 3.12.10 and native PostgreSQL 16. Its complete gate
reports 211 passed, 0 failed, 0 skipped, 94% overall branch coverage, and 92% coverage for
`app/services/employees.py`. Focused Stage 6 API/integration/security checks cover the exact
response, preconditions, CSRF/MFA/RBAC, tenant isolation, idempotency replay and key reuse,
same-key/different-key concurrency, rollback, applicability, active access, OpenAPI, no new Session,
and the live Stage 4→5→6 chain. Alembic remains at `0005_invitation_email_outbox`; the
empty-database migration test, current head check, and metadata no-drift check pass. CRA-38 is
accepted, Done, and published as part of the backend baseline through `abad74e`.

## Accepted CRA-40 Stage 7 evidence

The Full Regression and Acceptance Gate candidate uses Python 3.12.10 and native PostgreSQL 16.
Its complete gate reports 213 passed, 0 failed, 0 skipped, 94.05% exact overall statement/branch
coverage, and 91.80% aggregate coverage across the declared 17-file critical first-slice set.
The new acceptance file reports 2 passed; the adjacent auth/invitation/employee security and
integration suite reports 85 passed. Ruff format/check and strict mypy pass. Alembic remains at
`0005_invitation_email_outbox`; empty-database migration coverage, current-head verification, and
metadata no-drift all pass. The OpenAPI inventory contains 17 paths, all eight required first-slice
paths, and none of the forbidden internal secret fields. Canonical command and matrix evidence is
recorded in [`../docs/testing/vertical-slice-1-acceptance.md`](../docs/testing/vertical-slice-1-acceptance.md).
CRA-40 is accepted, Done, and published through `abad74e`.

## Accepted CRA-43 frontend commands and evidence

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

CRA-43 is accepted, Done, and published through `fa30a1f`. Its component gate contains 13 tests
across nine files. The browser gate executes one
complete route-mocked business path in three projects: 1440×1000 Admin desktop, 768×1024 compact,
and 375×812 employee mobile. Exact scope, RED/GREEN evidence, and limitations are recorded in
[`../docs/testing/frontend-vertical-slice-1-acceptance.md`](../docs/testing/frontend-vertical-slice-1-acceptance.md).

Coverage enables the standard `greenlet` concurrency tracer because SQLAlchemy's async adapter
crosses greenlet contexts. Without it, executed post-database branches are under-reported.

## Accepted CRA-49 evidence

The corrective accepted 2026-08-28 gate reports 270 passed, 0 failed, 0 skipped with 89% overall
statement/branch coverage on Python 3.12.10 and native PostgreSQL 16. Denys accepted the precise
coverage closure as at least 80% overall coverage with branch tracking, complete mandatory-scenario
mapping, and explicit concurrency/security proof; no undeclared critical file set is selected
retroactively. Ruff format/check, strict
mypy, Alembic head `0007_menu_import_review`, current-head validation, migration round-trips, and
metadata no-drift all pass. The frontend reports 19 Vitest tests and 6 Playwright tests passing,
with Prettier, ESLint, TypeScript, and production build green. The ten-part implementation ends at
`22927f7`; the corrective acceptance tail is published through `8028d6e`.

## Accepted CRA-54 evidence

The accepted 2026-08-28 gate reports 318 passed, 0 failed, 0 skipped with 88% overall
statement/branch coverage and 80% aggregate coverage across the predeclared seven-file critical
Training set on Python 3.12.10 and native PostgreSQL 16. Ruff format/check and strict mypy pass.
Alembic head is `0008_training_content`; empty-database upgrade, the Training migration round-trip,
current-head validation, and metadata no-drift pass. The frontend reports 27 Vitest tests and
9 Playwright tests passing, with Prettier, ESLint, TypeScript, and production build green.

Denys accepted the candidate and authorized fast-forward publication of its nine checkpoints to
`origin/main` through `d955f6a`. Railway/provider smoke, deployment, PR, merge, and production
configuration were not performed.

## Accepted CRA-57 evidence

The 2026-08-29 local gate reports 363 passed, 0 failed, 0 skipped with 88% overall
statement/branch coverage and 87% aggregate coverage across the seven Slice 4 service files on
Python 3.12.10 and native PostgreSQL 16. Ruff format/check and strict mypy pass. Alembic head is
`0009_assignment_completion_rollout`; current-head, empty-database/round-trip coverage and
metadata no-drift pass. The frontend reports 35 Vitest tests and 12 Playwright executions with
Prettier, ESLint, TypeScript, and production build green.

Denys accepted the implementation and authorized ordinary fast-forward publication of the nine
checkpoint range `5823a0e..d4e0184`. The range is published without history rewriting. No PR,
merge, provider, deployment, production configuration, or production-data action was performed.

## Local CRA-61 candidate evidence

The 2026-08-29 local gate reports 424 passed, 0 failed, 0 skipped with 88% overall
statement/branch coverage and 86% aggregate coverage across the predeclared five critical Slice 5
services on Python 3.12.10 and native PostgreSQL 16. Ruff format/check and strict mypy pass.
Alembic head is `0013_question_templates`; 13 migration tests, clean upgrade, current-head validation
and metadata no-drift pass. The frontend reports 45 Vitest tests and 15 Playwright executions,
with Prettier, ESLint, TypeScript and production build green.

This is not accepted or published evidence until Denys explicitly accepts CRA-61. No push, PR,
merge, provider or deployment action was performed.
