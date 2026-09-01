# HoReCa Project Context

## Purpose

HoReCaFam is the repository for the HoReCa Training Platform. Backend MVP Vertical Slice 1 through
CRA-40 and Frontend MVP Vertical Slice 1 through CRA-43 are accepted, Done, and fast-forward
published on `origin/main`. The CRA-43 implementation series ends at `fa30a1f`; accepted CRA-46
documentation advances the published `origin/main` baseline to `586f8c5`. CRA-47 planning for Menu
Slice 2 is accepted and Done. The CRA-48 documentation checkpoint `3b95b3c` and its corrective
publication record are published; CRA-48 is Done. CRA-49 Menu Source of Truth is accepted and
fast-forward published on `origin/main` through corrective checkpoint `8028d6e`. CRA-53 planning
and CRA-54 implementation for MVP Vertical Slice 3 — Training Content are accepted and Done.
CRA-54 is fast-forward published through `d955f6a`, and CRA-55 advances the prior documentation
baseline to `afc607a`. CRA-56 Slice 4 planning and CRA-57 implementation are accepted and Done.
CRA-57 adds Assignment, Completion, Progress and Rollout as nine fast-forward-published checkpoints
through `d4e0184`; the CRA-58 documentation checkpoint containing this record follows that range.
CRA-60 Slice 5 planning is accepted and Done. CRA-61 Interactive Training is accepted and Done as
the eleven-commit local range `93ce970..614da3d`; CRA-62 governs repository synchronization and
publication. CRA-63 planning and CRA-64 Practice are accepted and Done; the exact eight-commit
range is `74c5741..cc1c05a`, and CRA-65 synchronization is published through `4164b9c`. CRA-66
Final Exam planning and CRA-67 Final Exam/canonical Results are accepted and Done; CRA-67 is the
exact eight-checkpoint range `6be8f4d..703872b`, and CRA-68 is Done and published through
`9ef9fe1`. CRA-70 is the active bounded documentation-only checkpoint with one authorized local
commit and no push. CRA-69 Slice 8 planning is Backlog and draft v1 remains unaccepted. CRA-42 is
unrelated Backlog work. Broader production
administration,
providers/workers, PR, merge, deployment, and production configuration require separate approval
or later bounded issues.

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
detail. The corrective full gate is `270 passed / 0 failed / 0 skipped` with 89% backend coverage,
19 Vitest tests, 6 Playwright tests, and no Alembic drift. The ten implementation checkpoints end
at `22927f7`; the corrective acceptance tail is fast-forward published through `8028d6e`. See
[`docs/testing/menu-slice-2-acceptance.md`](docs/testing/menu-slice-2-acceptance.md).

[CRA-54](https://linear.app/craftspacee/issue/CRA-54/implement-mvp-vertical-slice-3-training-content)
is accepted, Done, and published through `d955f6a`. It adds Location-owned versioned Training
content, typed lesson blocks, private assets, atomic publication, protected Admin authoring, and
Active Employee own-Location current-Published read-only Learning. The accepted gate reports 318
backend tests, 88% overall statement/branch coverage, 80% aggregate critical Training coverage, 27
Vitest tests, 9 Playwright tests, Alembic head `0008_training_content`, and no metadata drift. See
[`docs/testing/training-slice-3-acceptance.md`](docs/testing/training-slice-3-acceptance.md).

[CRA-57](https://linear.app/craftspacee/issue/CRA-57) is accepted, Done and published through
`d4e0184`. It adds version audiences, shared applicability, immutable Assignment lineage,
explicit Lesson Completion, derived Progress, replacement-Version Rollout preview/rules/confirm,
transactional provider-free notification jobs, Admin assignment/rollout controls, and
assignment-aware Employee Learning. The local gate reports 363 backend tests, 88% overall and 87%
aggregate Slice 4 service coverage, Alembic head `0009_assignment_completion_rollout`, 35 Vitest
tests, and 12 Playwright executions. See
[`docs/testing/training-assignment-slice-4-acceptance.md`](docs/testing/training-assignment-slice-4-acceptance.md).
The implementation is accepted and published; it was not deployed and made no provider calls.

[CRA-61](https://linear.app/craftspacee/issue/CRA-61) is accepted and Done. It adds Question
Candidate/Bank and assessment persistence through `0013_question_templates`, deterministic
category, component, allergen and description Candidate generation with provenance and human
publication, per-Lesson readiness, immutable five-question Attempts, idempotent Answers,
immediate feedback, device takeover, Results, Latest/Best history, and responsive Admin/Employee
UI. The accepted gate reports 424 backend tests, 88% overall and 86% aggregate critical Slice 5
coverage, 45 Vitest tests and 15 Playwright executions. Exact evidence and the accepted remaining
source-bound limitations are recorded in
[`docs/testing/interactive-training-slice-5-acceptance.md`](docs/testing/interactive-training-slice-5-acceptance.md).
CRA-62 is the bounded repository synchronization/publication checkpoint. Deployment and provider
execution remain separately gated and unperformed.

[CRA-63](https://linear.app/craftspacee/issue/CRA-63) Practice planning is accepted and Done.
[CRA-64](https://linear.app/craftspacee/issue/CRA-64) Practice is accepted and Done. Its exact
eight-checkpoint range `74c5741..cc1c05a` adds generic 5/10/20 assessment persistence through
`0014_practice_persistence`, source-safe whole-menu Practice readiness, immutable ten-Question
Attempts, feedback-free Answers, explicit finish, Knowledge, durable Final Exam eligibility,
Latest/Best history, Admin readiness and responsive Employee UI. Evidence is in
[`docs/testing/practice-slice-6-acceptance.md`](docs/testing/practice-slice-6-acceptance.md).
[CRA-65](https://linear.app/craftspacee/issue/CRA-65) is Done and published through `4164b9c`.
[CRA-66](https://linear.app/craftspacee/issue/CRA-66) Final Exam planning is accepted and Done.
[CRA-67](https://linear.app/craftspacee/issue/CRA-67) is accepted and Done as
`6be8f4d..703872b`; it adds Final Exam, certification and canonical Results.
[CRA-68](https://linear.app/craftspacee/issue/CRA-68) is accepted, Done and published through
`9ef9fe1`. [CRA-70](https://linear.app/craftspacee/issue/CRA-70) is the active bounded
documentation-only synchronization checkpoint. [CRA-69](https://linear.app/craftspacee/issue/CRA-69)
is Backlog; its Slice 8 planning draft v1 remains unaccepted and separate from implementation.

## Repository map

- [`backend/app`](backend/app): accepted runtime through CRA-67 Final Exam and Results.
- [`backend/migrations`](backend/migrations): Alembic environment and accepted revisions through
  head `0014_practice_persistence`.
- [`backend/tests`](backend/tests): API, unit, integration, and migration tests.
- [`backend/pyproject.toml`](backend/pyproject.toml): Python requirements and tool configuration.
- [`frontend`](frontend): accepted experiences through CRA-67 Admin Results and Employee Final
  Exam, component tests and Playwright evidence.
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
