# Testing Context

Canonical test strategy, stage acceptance criteria, and Definition of Done remain in
[CRA-13](https://linear.app/craftspacee/issue/CRA-13/define-backend-test-strategy-and-vertical-slice-acceptance-criteria)
and the active bounded implementation issue. Exact local commands and environment safeguards are
maintained in [`../../.harness/TESTING.md`](../../.harness/TESTING.md).

## Current test layout

- `backend/tests/api`: application factory, health contract, request ID, validation, and safe error
  behavior through the ASGI path.
- `backend/tests/unit`: required configuration and fail-closed test database rules.
- `backend/tests/integration`: live async SQLAlchemy/asyncpg round-trip against PostgreSQL 16.
- `backend/tests/migration`: Alembic head smoke and the prohibition on runtime `create_all`.

## Isolation rules

- Use real PostgreSQL 16, never SQLite, for persistence/migration behavior.
- Use only `APP_ENV=test` and a database named `horeca_test` or an approved worker derivative.
- Keep test credentials in ignored local configuration and never print them.
- Tests must be deterministic and independent of execution order.
- Report PostgreSQL skips explicitly; a no-skip gate requires the dedicated database boundary.

## Accepted Stage 0 baseline

[CRA-20](https://linear.app/craftspacee/issue/CRA-20/backend-mvp-vertical-slice-1-stage-0-api-foundation)
was accepted on 2026-08-26 with:

- Python 3.12.10;
- native PostgreSQL 16.15;
- 22 passed, 0 failed, 0 skipped;
- 95% Stage 0 coverage;
- a live asyncpg/SQLAlchemy round-trip;
- a fresh database at Alembic head `0001_stage0`;
- Ruff format/check and strict mypy passing.

These are historical accepted results. Any future behavior change must produce new task-specific
RED/GREEN evidence and rerun the checks proportionate to its risk.
