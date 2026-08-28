# HoReCa Project Context

## Purpose

HoReCaFam is the repository for the HoReCa Training Platform. Backend MVP Vertical Slice 1 through
CRA-40 and Frontend MVP Vertical Slice 1 through CRA-43 are accepted, Done, and fast-forward
published on `origin/main`. The CRA-43 implementation series ends at `fa30a1f`; accepted CRA-46
documentation advances the published `origin/main` baseline to `586f8c5`. CRA-47 planning for Menu
Slice 2 is accepted and Done. The CRA-48 documentation checkpoint `3b95b3c` and its corrective
publication record are published; CRA-48 is Done. CRA-49 Menu Source of Truth is accepted and
fast-forward published on `origin/main` through `22927f7`. CRA-42 is unrelated Backlog work.
Training-domain expansion,
broader production administration, providers/workers, push, PR, merge, deployment, and production
configuration require separate approval or later bounded issues.

This document gives a new agent enough durable local context to orient safely. It intentionally
does not reproduce full product, API, data, RBAC, or test-stage contracts.

## Canonical product sources

Start with the Linear
[HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974),
then follow the source order it defines:

- [CRA-12](https://linear.app/craftspacee/issue/CRA-12/define-rest-api-contract-and-pydantic-schemas)
  for the final REST API contract and approved runtime behavior.
- [CRA-10](https://linear.app/craftspacee/issue/CRA-10/design-database-schema-and-entity-relationships)
  for the current database design, migration order, and RBAC where consistent with CRA-12.
- [CRA-13](https://linear.app/craftspacee/issue/CRA-13/define-backend-test-strategy-and-vertical-slice-acceptance-criteria)
  for backend test strategy and vertical-slice acceptance gates.
- The single active bounded Linear issue for exact scope, permissions, and evidence requirements.

Repository summaries are navigation aids. A consequential product/API/data/test decision is not
canonical until it is recorded in the applicable Linear source.

## Verified implementation boundary

[CRA-20](https://linear.app/craftspacee/issue/CRA-20/backend-mvp-vertical-slice-1-stage-0-api-foundation)
Stage 0 is accepted and Done. Its repository foundation contains:

- a Python 3.12 FastAPI application factory;
- the versioned `/api/v1` boundary and health route;
- request ID correlation and unified API errors;
- typed configuration;
- async SQLAlchemy 2 and asyncpg session infrastructure;
- Alembic with the base `0001_stage0` revision;
- fail-closed test database safety checks;
- API, unit, real-PostgreSQL integration, and migration tests;
- a reserved, empty frontend boundary.

[CRA-28](https://linear.app/craftspacee/issue/CRA-28/implement-backend-mvp-vertical-slice-1-stage-1-identity-persistence)
is accepted and adds the Stage 1 persistence checkpoint:

- Organization, Location, OperationalRole, User, OrganizationMembership, EmployeeProfile, and
  AuditEvent SQLAlchemy models;
- canonical normalized email storage;
- PostgreSQL tenant-ownership, lifecycle, uniqueness, and audit constraints;
- Alembic revision `0002_identity_persistence`;
- real-PostgreSQL identity and migration tests.

[CRA-30](https://linear.app/craftspacee/issue/CRA-30/implement-backend-mvp-vertical-slice-1-stage-2-auth-session-csrf-mfa)
is accepted and adds Stage 2: Argon2id credentials, non-enumerating login, opaque server-side
sessions, secure cookies, synchronizer CSRF, current-session logout, encrypted TOTP completion,
PostgreSQL abuse throttling, and deny-by-default RBAC dependencies.

[CRA-32](https://linear.app/craftspacee/issue/CRA-32/implement-backend-mvp-vertical-slice-1-stage-3-invitation)
is accepted and adds Stage 3 invitation administration: lifecycle persistence, deterministic
versioned tokens, transactional email outbox state, persistent idempotency/rate limits, and
protected create/resend/revoke plus public token validation routes.

[CRA-34](https://linear.app/craftspacee/issue/CRA-34/implement-backend-mvp-vertical-slice-1-stage-4-invitation-acceptance)
is accepted and adds Stage 4: atomic new/existing-account invitation acceptance, Pending
Membership and placeholder EmployeeProfile creation, an opaque Session, and safe audit/cookie
integration. Provider delivery, worker deployment, invitation list/detail routes, password
recovery, MFA enrollment/recovery, training, and the frontend are not implemented.

[CRA-36](https://linear.app/craftspacee/issue/CRA-36/implement-backend-mvp-vertical-slice-1-stage-5-pendingadmin-profile)
is accepted, Done, and published through `de6dd84`. It adds Stage 5: scoped
Organization/Location/OperationalRole reads, Admin Employee list/detail, own read-only operational
profiles, and Pending-only profile PATCH with atomic safe audit. It deliberately does not activate
Membership or create Assignments.

[CRA-37](https://linear.app/craftspacee/issue/CRA-37/plan-backend-mvp-vertical-slice-1-stage-6-explicit-activation)
is accepted and Done. It locks the Stage 6 Explicit Activation contract and five-checkpoint map.
[CRA-38](https://linear.app/craftspacee/issue/CRA-38/implement-backend-mvp-vertical-slice-1-stage-6-explicit-activation)
is accepted and Done. Its local implementation adds the exact protected
`POST /api/v1/organizations/{organization_id}/employees/{employee_id}/activate` contract, locked
Pending-to-Active transition, active-reference revalidation, existing-record idempotency, safe
`employee_activated` audit, derived active training participation, and an explicit zero-output
applicability boundary. It creates no new Session, Assignment, notification, content record, job,
provider call, schema object, or migration. CRA-38 and CRA-40 are accepted, Done, and published
through `abad74e`; the complete backend acceptance chain and evidence matrix remain historical
evidence for the frontend slice.

[CRA-49](https://linear.app/craftspacee/issue/CRA-49/implement-menu-source-of-truth-slice-2)
is accepted and published. It adds Menu persistence and migrations through
`0007_menu_import_review`, revision-guarded Draft hierarchy/facts, protected JSON review and atomic
publication, published-only Employee API reads, Admin lifecycle UI, and Employee mobile search/
detail. The fresh full gate is `267 passed / 0 failed / 0 skipped` with 87% backend coverage,
19 Vitest tests, 6 Playwright tests, and no Alembic drift. The ten implementation checkpoints are
fast-forward published through `22927f7`; see
[`docs/testing/menu-slice-2-acceptance.md`](docs/testing/menu-slice-2-acceptance.md).

## Repository map

- [`backend/app`](backend/app): accepted Stage 0–6 runtime plus accepted CRA-49 Menu behavior.
- [`backend/migrations`](backend/migrations): Alembic environment and accepted revisions through
  CRA-49 head `0007_menu_import_review`.
- [`backend/tests`](backend/tests): API, unit, integration, and migration tests.
- [`backend/pyproject.toml`](backend/pyproject.toml): Python requirements and tool configuration.
- [`frontend`](frontend): accepted CRA-43 React frontend plus the accepted CRA-49 Menu experience,
  unit/component tests, and Playwright acceptance.
- [`docs/architecture`](docs/architecture): verified local architecture summaries.
- [`docs/decisions`](docs/decisions): repository-local engineering decision index.
- [`docs/testing`](docs/testing): testing structure and accepted evidence index.
- `Photos/`: project assets for
  [CRA-19 Bacara Welcome / homepage](https://linear.app/craftspacee/issue/CRA-19/design-bacara-welcome-brand-intro-responsive-mockups),
  deferred from the initial backend/docs baseline and outside the accepted Stage 0 architecture
  boundary. Moving, renaming, optimizing, staging, or publishing them requires a separate bounded
  CRA-19 implementation/asset commit map.

## Current construction rule

Work proceeds by one bounded vertical stage at a time. Passing one stage permits only the next
explicitly approved planning or baseline action. See [`STATUS.md`](STATUS.md) for the current
checkpoint and next allowed step.
