# Testing Context

Canonical test strategy, stage acceptance criteria, and Definition of Done remain in
[CRA-13](https://linear.app/craftspacee/issue/CRA-13/define-backend-test-strategy-and-vertical-slice-acceptance-criteria)
and the active bounded implementation issue. Exact local commands and environment safeguards are
maintained in [`../../.harness/TESTING.md`](../../.harness/TESTING.md).

## Current test layout

- `backend/tests/api`: application factory, health/errors, auth/session/CSRF/logout/MFA/RBAC, and
  invitation lifecycle behavior through the ASGI path with real PostgreSQL state.
- `backend/tests/unit`: required configuration, fail-closed test database rules, canonical email
  normalization, and deterministic versioned invitation tokens.
- `backend/tests/integration`: live async SQLAlchemy/asyncpg round-trip, persistence constraints,
  idempotency concurrency, and transactional invitation-delivery state against PostgreSQL 16.
- `backend/tests/migration`: Alembic head/schema/drift checks and the prohibition on runtime
  `create_all`.
- `backend/tests/factories` and `backend/tests/conftest.py`: deterministic identity objects and
  guarded real-PostgreSQL cleanup fixtures.

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

## Accepted CRA-28 checkpoint

The accepted Stage 1 checkpoint reports:

- Python 3.12.10 and native PostgreSQL 16.15;
- 47 passed, 0 failed, 0 skipped;
- 97% statement/branch coverage;
- Alembic head `0002_identity_persistence` and no metadata drift;
- focused tenant-ownership, lifecycle, email uniqueness, audit, and migration proof.

Canonical RED/GREEN evidence and limitations are recorded in CRA-28.

## Accepted CRA-30 checkpoint

The accepted Stage 2 checkpoint reports Python 3.12.10, PostgreSQL 16.15, 92 passed, 0 failed,
0 skipped, 94% overall statement/branch coverage, and 92% critical auth coverage. A dedicated
`horeca_test` base→`0003_auth_security` cycle passes and Alembic reports no metadata drift.
Canonical RED/GREEN evidence and acceptance are recorded in CRA-30.

## Accepted CRA-32 checkpoint

The accepted local invitation checkpoint reports:

- Python 3.12.10 and native PostgreSQL 16.15;
- 156 passed, 0 failed, 0 skipped;
- 94% overall statement/branch coverage and 90% aggregate coverage across invitation routes,
  RBAC dependency, token, idempotency, delivery, and lifecycle services;
- Alembic head `0005_invitation_email_outbox`, migration downgrade/upgrade coverage, and no
  metadata drift;
- a live async HTTP create → validate → resend → old-token rejection → revoke lifecycle.

CRA-32 remains the canonical evidence source and is accepted and Done in Linear. Its six local
commits are not yet published.

## CRA-34 Stage 4 local candidate

The invitation-acceptance candidate reports:

- Python 3.12.10 and native PostgreSQL 16.15;
- 180 passed, 0 failed, 0 skipped;
- 94% overall statement/branch coverage and 93% aggregate critical acceptance coverage;
- Alembic head `0005_invitation_email_outbox`, the empty-database migration test, and no metadata
  drift;
- focused API, service, concurrency, rollback, throttle, and tenant-isolation proof.

The first full gate found only a stale deterministic test clock; after moving that test-only clock
forward, the focused API suite reported 12 passed and the full gate above was green. CRA-34 remains
In Progress until Denys accepts the local candidate.
