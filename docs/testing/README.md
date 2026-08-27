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

CRA-32 remains the canonical evidence source and is accepted, Done, and published.

## Accepted CRA-34 Stage 4 checkpoint

The accepted invitation-acceptance checkpoint reports:

- Python 3.12.10 and native PostgreSQL 16.15;
- 180 passed, 0 failed, 0 skipped;
- 94% overall statement/branch coverage and 93% aggregate critical acceptance coverage;
- Alembic head `0005_invitation_email_outbox`, the empty-database migration test, and no metadata
  drift;
- focused API, service, concurrency, rollback, throttle, and tenant-isolation proof.

The first full gate found only a stale deterministic test clock; after moving that test-only clock
forward, the focused API suite reported 12 passed and the full gate above was green. CRA-34 is Done,
and its four commits are published through `9fd2130`.

## Accepted CRA-36 Stage 5 checkpoint

The Pending/Admin Profile Setup checkpoint reports:

- Python 3.12.10 and native PostgreSQL 16;
- 195 passed, 0 failed, 0 skipped;
- 94% overall branch coverage and 92% aggregate critical Stage 5 coverage;
- 15 focused Stage 5 API/integration tests covering reads, cursor/filter behavior, Pending PATCH,
  CSRF/MFA/RBAC, tenant isolation, rollback, OpenAPI, and the Stage 4→5 live chain;
- Alembic head `0005_invitation_email_outbox`, empty-database migration coverage, current head,
  and no metadata drift.

CRA-36 is accepted. Its exact commit and publication evidence remains canonical in Linear and Git.

## Accepted CRA-38 Stage 6 checkpoint

The Explicit Activation candidate reports:

- Python 3.12.10 and native PostgreSQL 16;
- 211 passed, 0 failed, 0 skipped;
- 94% overall branch coverage and 92% coverage for `app/services/employees.py`;
- focused API/integration/security proof for the exact response, preconditions, CSRF/MFA/RBAC,
  tenant isolation, safe audit, rollback, idempotency replay/reuse/concurrency, zero applicability,
  immediate Active access, OpenAPI, no new Session, and the Stage 4→5→6 chain;
- Alembic head `0005_invitation_email_outbox`, empty-database migration coverage, current head,
  and no metadata drift.

CRA-38 is accepted, Done, and published as part of the backend baseline through `abad74e`.

## Accepted CRA-40 Stage 7 checkpoint

The full Vertical Slice 1 regression and acceptance candidate reports:

- Python 3.12.10 and native PostgreSQL 16;
- 213 passed, 0 failed, 0 skipped;
- 94.05% exact overall statement/branch coverage;
- 91.80% aggregate coverage across the declared 17-file critical first-slice set;
- 2 focused Stage 7 acceptance tests and 85 adjacent auth/invitation/employee tests passing;
- Ruff format/check and strict mypy passing;
- Alembic head `0005_invitation_email_outbox`, current head, empty-database migration coverage,
  and no metadata drift;
- 17 OpenAPI paths, all eight required first-slice paths present, and zero forbidden internal
  secret-field hits.

The complete requirement matrix, exact commands, coverage formula, security review, limitations,
and staging exclusion are recorded in
[`vertical-slice-1-acceptance.md`](vertical-slice-1-acceptance.md). CRA-40 is accepted, Done, and
published through `abad74e`.

## Current CRA-43 frontend candidate

The frontend candidate adds a contract-driven React implementation for login/MFA, both invitation
entry boundaries, Pending Employee state, Admin employee profile setup, explicit Activation, and a
truthful Active Employee zero-assignment home. Vitest/Testing Library covers 13 component and API
behaviors. Playwright repeats the complete business path on desktop, compact, and mobile
viewports. See [`frontend-vertical-slice-1-acceptance.md`](frontend-vertical-slice-1-acceptance.md)
for the exact matrix, commands, results, and exclusions.
