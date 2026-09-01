# Testing Context

Canonical test strategy, stage acceptance criteria, and Definition of Done remain in
[CRA-13](https://linear.app/craftspacee/issue/CRA-13/define-backend-test-strategy-and-vertical-slice-acceptance-criteria)
and the active bounded issue. Exact local commands and environment safeguards are
maintained in [`../../.harness/TESTING.md`](../../.harness/TESTING.md).

The published repository includes the accepted CRA-48 corrective record after `3b95b3c`. CRA-43
test evidence remains anchored to `fa30a1f`. CRA-47 planning and CRA-48 documentation are Done.
CRA-49 is accepted and fast-forward published through corrective checkpoint `8028d6e`; its runtime
evidence is recorded below. CRA-53 planning and CRA-54 implementation are accepted and Done.
CRA-54 is fast-forward published through `d955f6a`, and CRA-55 advances the prior documentation
baseline to `afc607a`. CRA-56 and CRA-57 are accepted and Done; CRA-57 is fast-forward published
through `d4e0184`, followed by CRA-58. CRA-60 planning and CRA-61 Interactive Training are accepted
and Done; CRA-62 governs their repository synchronization and publication evidence. CRA-63
planning and CRA-64 Practice are accepted and Done; CRA-65 synchronization is published through
`4164b9c`. CRA-66 Final Exam planning and CRA-67 implementation are accepted and Done. CRA-68 is
Done and published through `9ef9fe1`. CRA-69 Slice 8 planning and CRA-71 Attention and Retakes are
accepted and Done. CRA-74 ordinary fast-forward published CRA-70 at `5352f89`, CRA-71 as
`62a80a0..054d731`, and the CRA-72 documentation checkpoint through `4019262`; CRA-75 owns the
publication-state documentation checkpoint.

## Current test layout

- `backend/tests/api`: application factory, health/errors, auth/session/CSRF/logout/MFA/RBAC,
  invitation lifecycle, Admin Menu/import/publication, Employee published-Menu behavior, Admin
  Training/publication/Assignment/Rollout, and Employee assignment-aware Training/Completion
  behavior through the ASGI path with real PostgreSQL state.
- `backend/tests/unit`: required configuration, fail-closed test database rules, canonical email
  normalization, and deterministic versioned invitation tokens.
- `backend/tests/integration`: live async SQLAlchemy/asyncpg round-trip, persistence constraints,
  idempotency concurrency, transactional invitation delivery, Menu draft/facts/publication, and
  Training draft/content/assets/publication plus Assignment/Completion/Rollout state against
  PostgreSQL 16.
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

## Accepted CRA-43 frontend checkpoint

CRA-43 is accepted, Done, and fast-forward published through `fa30a1f`. It adds a contract-driven
React implementation for login/MFA, both invitation entry boundaries, Pending Employee state,
Admin employee profile setup, explicit Activation, and a truthful Active Employee zero-assignment
home. Vitest/Testing Library covers 13 component and API behaviors. Playwright repeats the complete
business path on desktop, compact, and mobile viewports. See
[`frontend-vertical-slice-1-acceptance.md`](frontend-vertical-slice-1-acceptance.md) for the exact
matrix, commands, results, and exclusions.

## Accepted CRA-49 checkpoint

The accepted gate reports Python 3.12.10 and native PostgreSQL 16:

- 270 passed, 0 failed, 0 skipped;
- 89% overall statement/branch coverage;
- accepted corrective coverage gate: at least 80% overall with branch tracking, every mandatory
  Slice 2 scenario mapped, and explicit concurrency/security proof; no post-hoc critical file set;
- Ruff format/check and strict mypy passing;
- Alembic head `0007_menu_import_review`, current head, migration round-trips, and no metadata
  drift;
- frontend Prettier/ESLint/TypeScript/build passing;
- 19 Vitest tests passing across 12 files;
- 6 Playwright tests passing across the desktop, compact, and mobile projects.

See [`menu-slice-2-acceptance.md`](menu-slice-2-acceptance.md) for the requirement matrix,
RED/GREEN evidence, security review, exact browser path, limitations, and exclusions. The ten
implementation checkpoints end at `22927f7`; the corrective acceptance tail is published through
`8028d6e`.

## Accepted CRA-54 checkpoint

The accepted gate reports Python 3.12.10 and native PostgreSQL 16:

- 318 passed, 0 failed, 0 skipped;
- 88% overall statement/branch coverage and 80% aggregate coverage across the predeclared
  seven-file critical Training set;
- Ruff format/check and strict mypy passing;
- Alembic head `0008_training_content`, current head, migration round-trip coverage, and no
  metadata drift;
- frontend Prettier/ESLint/TypeScript/build passing;
- 27 Vitest tests passing across 14 files;
- 9 Playwright tests passing across the desktop, compact, and mobile projects.

See [`training-slice-3-acceptance.md`](training-slice-3-acceptance.md) for the implemented boundary,
requirement matrix, RED/GREEN evidence, critical-file declaration, browser path, security review,
limitations, and explicit Slice 4 exclusions. Denys accepted the checkpoint and authorized
fast-forward publication through `d955f6a`; Railway/provider smoke, deployment, PR, and merge were
not performed.

## Accepted CRA-57 checkpoint

The local 2026-08-29 gate reports 363 backend tests, 88% overall statement/branch coverage, 87%
aggregate Slice 4 service coverage, Alembic head `0009_assignment_completion_rollout`, 35 Vitest
tests, and 12 Playwright executions across desktop, compact, and mobile projects. See
[`training-assignment-slice-4-acceptance.md`](training-assignment-slice-4-acceptance.md) for the
26-scenario matrix, exact boundary, security review, and limitations. Denys accepted CRA-57 and
authorized ordinary fast-forward publication of `5823a0e..d4e0184`; no deployment, provider, PR,
merge, or production action was performed.

## Accepted CRA-61 evidence

The 2026-08-29 local gate reports 424 backend tests, 88% overall statement/branch coverage, 86%
aggregate coverage across the predeclared five-file Slice 5 service set, Alembic head
`0013_question_templates`, 45 Vitest tests, and 15 Playwright executions across the approved
desktop, compact and mobile projects. The complete 27-scenario mapping, exact local boundary,
security review and remaining source-bound generation limitations are in
[`interactive-training-slice-5-acceptance.md`](interactive-training-slice-5-acceptance.md).

Denys accepted this evidence and the remaining source-bound generation limitations. CRA-62 governs
repository publication and exact remote evidence; PR, merge, provider and deployment actions remain
separately gated.

## Accepted CRA-64 Practice evidence

The accepted 2026-08-31 eight-checkpoint range implements the CRA-63 forty-scenario Practice
boundary:
ten distinct Menu Items, feedback-free Answer saves, explicit finish, Knowledge, critical-allergen
evidence, durable Final Exam eligibility, Admin readiness and responsive Employee UI. Exact
executed evidence, RED/GREEN corrections, limitations and the eight-checkpoint boundary are in
[`practice-slice-6-acceptance.md`](practice-slice-6-acceptance.md).

CRA-64 is Done and CRA-65 synchronization is published through `4164b9c`. No later push,
deployment, provider or production action is implied.

## Accepted CRA-67 Final Exam evidence

The accepted eight-checkpoint range implements balanced 20-question Final Exam readiness,
eligibility, feedback-free answer saves, confirmed atomic finish, exact 70% passing, certification,
history, responsive Employee execution and canonical Admin Results. The executed regression,
focused PostgreSQL concurrency proof, browser matrix, limitations and checkpoint boundary are in
[`final-exam-slice-7-acceptance.md`](final-exam-slice-7-acceptance.md).

CRA-67 and CRA-68 are Done, and the accepted repository baseline is published through `9ef9fe1`.
These results remain historical accepted evidence. No PR, merge, provider or deployment is implied.

## Accepted CRA-71 Attention and Retakes evidence

The accepted implementation reports 463 backend tests passed at 86% statement/branch
coverage; Ruff, strict mypy and Alembic upgrade/current/no-drift passed at
`0015_attention_retakes`. Prettier, ESLint,
TypeScript and production build passed; full Vitest reports 58 passed and full Playwright reports
27 passed across desktop, compact and mobile. The scenario-to-test map, focused evidence and known
approval gates are recorded in
[`attention-retakes-slice-8-acceptance.md`](attention-retakes-slice-8-acceptance.md). Denys accepted
this evidence and the exact eight-checkpoint range. CRA-74 ordinary fast-forward published it
through `4019262`; PR, merge and deployment remain separately gated.
