# Backend Foundation

This directory contains the accepted and published backend MVP Vertical Slice 1 through CRA-40
plus the accepted CRA-49 Menu Source of Truth runtime and corrective acceptance tail, published
through `8028d6e`. CRA-49 adds
Location-owned versioned Menu persistence, Draft/import/publication administration, and a
published-only Employee reference API. Python 3.12 and PostgreSQL 16 are the approved runtime
versions.

Before backend work, read [`AGENTS.md`](AGENTS.md) and the repository
[`../AGENTS.md`](../AGENTS.md). Linear remains canonical for product/API/data/test-stage
contracts.

## Local setup

From the repository root:

```powershell
rtk py -3.12 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
```

Real PostgreSQL 16 is required for integration and migration tests. Two local boundaries are
supported:

- Docker Compose through `compose.test.yml` when Docker is available.
- Native PostgreSQL 16 as the accepted local fallback.

Keep local values only in ignored `.env` or `.env.test` files. Use obvious placeholders when
creating the test configuration; never commit or print the real URL:

```dotenv
APP_ENV=test
TEST_DATABASE_URL=<local-test-postgresql-async-url>
DATABASE_URL=<same-local-test-postgresql-async-url>
```

Use only the dedicated test database when running destructive test setup or cleanup. Follow the
secret-safe environment loading procedure in
[`../.harness/TESTING.md`](../.harness/TESTING.md).

The application is exposed through the factory `app.main:create_app`; configuration is required
and there is no SQLite fallback. SQLAlchemy metadata covers identity/authentication records plus
invitations, API idempotency, invitation rate-limit buckets, background jobs, and email delivery
state, plus CRA-49 Menu versions, hierarchy, facts/provenance, deltas, import review, and publication
records. Alembic is the only schema-management path; runtime and tests must not call `create_all`.

## Quality and test commands

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

`assert_safe_test_database` rejects cleanup unless `APP_ENV=test` and the resolved database name is `horeca_test` or a worker-scoped derivative such as `horeca_test_gw0`.

The complete no-skip gate and CRA-20/CRA-28/CRA-30/CRA-32 evidence index are documented in
[`../docs/testing/README.md`](../docs/testing/README.md).

The corrective accepted CRA-49 gate reports 270 passed, 0 failed, 0 skipped, 89% overall
statement/branch coverage, Alembic head `0007_menu_import_review`, and no metadata drift. It also
proves same-key/different-key Draft, Import Resolution/Confirm, and Publish concurrency plus stable
Employee Component search/cursor pagination. See
[`../docs/testing/menu-slice-2-acceptance.md`](../docs/testing/menu-slice-2-acceptance.md).
