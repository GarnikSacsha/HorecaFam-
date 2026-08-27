# HoReCa Repository Status

**Snapshot date:** 2026-08-27
**Current bounded task:**
[CRA-43 — Implement Frontend MVP Vertical Slice 1](https://linear.app/craftspacee/issue/CRA-43/implement-frontend-mvp-vertical-slice-1-foundation-auth-pending-and),
routed through the Linear
[START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).
CRA-41 is accepted and Done. Denys authorized CRA-43 implementation, its exact dependency set, and
its six-checkpoint local commit map on 2026-08-27. CRA-42 is an unrelated Backlog task. Push, PR,
merge, deployment, providers, and later stages remain separate gates. This document records durable
checkpoints; it does not expand CRA-43 beyond its explicit approvals.

## Accepted implementation and planning checkpoints

- CRA-20 Stage 0 is accepted and Done.
- CRA-21 repository baseline and agent context is accepted and Done.
- CRA-22 atomic commit workflow is accepted and Done.
- CRA-23 retrospective selective first-baseline commit map is accepted and Done.
- CRA-24 repository-context synchronization is accepted and Done.
- CRA-25 selective five-commit baseline execution is accepted and Done.
- CRA-26 initial baseline publication and state synchronization is accepted and Done.
- CRA-27 Stage 1 identity-persistence implementation plan is accepted and Done.
- CRA-28 Stage 1 identity-persistence implementation is accepted and Done.
- CRA-29 Stage 2 auth/session/CSRF/MFA/RBAC plan is accepted and Done.
- CRA-30 Stage 2 auth/session/CSRF/MFA/RBAC implementation is accepted, Done, and published.
- CRA-31 Stage 3 invitation plan is accepted and Done.
- CRA-32 Stage 3 invitation administration implementation is accepted, Done, and published.
- CRA-33 Stage 4 invitation-acceptance plan is accepted and Done.
- CRA-34 Stage 4 invitation-acceptance implementation is accepted, Done, and published.
- CRA-35 Stage 5 Pending/Admin Profile Setup plan is accepted and Done.
- CRA-36 Stage 5 Pending/Admin Profile Setup implementation is accepted, Done, and published through
  `de6dd84`. Its five selective local commits and fast-forward push were explicitly authorized on
  2026-08-27.
- CRA-37 Stage 6 Explicit Activation plan and five-checkpoint map are accepted and Done.
- CRA-38 Stage 6 Explicit Activation implementation is accepted, Done, and published.
- CRA-39 Stage 7 Full Regression and Acceptance Gate plan is accepted and Done.
- CRA-40 Stage 7 implementation is accepted, Done, and published through `abad74e`.
- CRA-41 Frontend MVP Vertical Slice 1 plan and six-checkpoint map are accepted and Done.
- CRA-43 Frontend MVP Vertical Slice 1 implementation is In Progress with six authorized local
  commits; all remote and deployment actions remain separate gates.
- Accepted runtime: Python 3.12.10 and PostgreSQL 16.15.
- Accepted local database boundaries: Docker Compose PostgreSQL 16 or native PostgreSQL 16,
  always with `APP_ENV=test` and an explicitly test-scoped database.
- Final CRA-20 evidence: `22 passed / 0 failed / 0 skipped`, 95% Stage 0 coverage, Alembic head
  `0001_stage0`, and a live async SQLAlchemy/asyncpg round-trip on PostgreSQL 16.15.
- The canonical five-commit baseline map and its exact selective path arrays are recorded in
  [CRA-23](https://linear.app/craftspacee/issue/CRA-23/prepare-retrospective-selective-first-baseline-commit-map).

The Stage 0 gate was rerun successfully during the selective baseline execution recorded in
CRA-25; the canonical acceptance history remains in CRA-20.

## Accepted Stage 1 checkpoint

- CRA-28 implements the accepted Stage 1 identity persistence boundary.
- Accepted gate: Python 3.12.10, PostgreSQL 16.15, `47 passed / 0 failed / 0 skipped`, 97%
  statement/branch coverage, Alembic head `0002_identity_persistence`, and no metadata drift.
- The candidate adds only Organization, Location, OperationalRole, User,
  OrganizationMembership, EmployeeProfile, and AuditEvent persistence.
- CRA-30 implements the accepted Stage 2 authentication/session/CSRF/MFA/RBAC boundary.
- Accepted CRA-30 gate: Python 3.12.10, PostgreSQL 16.15,
  `92 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 92% critical auth
  coverage, Alembic head
  `0003_auth_security`, and no metadata drift.

## Accepted and published Stage 3 checkpoint

- CRA-32 implements the accepted invitation lifecycle boundary: persistence, transactional email
  outbox, deterministic versioned tokens, persistent idempotency and rate limits, create,
  validate, resend, and revoke.
- Accepted local gate: Python 3.12.10, PostgreSQL 16.15,
  `156 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 90% critical
  invitation coverage, Alembic head `0005_invitation_email_outbox`, and no metadata drift.
- Provider calls, a worker/runtime deployment, invitation acceptance, list/detail endpoints, and
  non-test provisioning remain outside CRA-32.
- Denys accepted CRA-32 on 2026-08-27. Linear records it as Done, and its six commits are published.

## Accepted and published Stage 4 checkpoint

- CRA-34 adds only `POST /api/v1/invitations/accept`: locked Invitation authority, new/existing
  User branches, Pending Membership and placeholder EmployeeProfile creation, an opaque Session,
  a safe audit trail, and the Secure HttpOnly cookie response.
- Acceptance is atomic and tenant-isolated. Same-token and same-email races have one winner;
  failure paths roll back domain, session, and audit mutations. Acceptance never activates a
  membership or records MFA verification.
- Current local gate: Python 3.12.10, PostgreSQL 16.15,
  `180 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 93% aggregate
  critical acceptance coverage, Alembic head `0005_invitation_email_outbox`, and no metadata
  drift.
- The first full gate exposed a stale deterministic test clock, not a product failure. The clock
  was moved forward without changing production behavior; the focused API suite then reported
  `12 passed` and the full gate was green.
- Denys accepted CRA-34 on 2026-08-27. Linear records it as Done, and its four commits are published.

## Accepted and published Stage 5 checkpoint

- CRA-36 adds MFA-verified Admin Organization/Location/OperationalRole reads, cursor-paginated
  Employee list/detail, authenticated own read-only operational profiles, and CSRF-protected
  Pending-only profile setup.
- Employee identity is `EmployeeProfile.id`; every Admin query remains Organization-scoped.
  Foreign Employee/reference probes are non-enumerating, archived references remain explainable
  but are not selectable, and profile completeness is derived.
- Successful profile update appends a safe `employee_profile_updated` audit in the same transaction.
  Name/email values are not copied into audit. Forced commit failure rolls back domain and audit.
- Membership remains Pending in CRA-36. That issue deliberately excludes Stage 6 Activation,
  applicability, Assignments, notifications, Active/Disabled lifecycle changes, providers,
  frontend, and deployment.
- Accepted gate: Python 3.12.10, PostgreSQL 16, `195 passed / 0 failed / 0 skipped`, 94% overall
  branch coverage, and 92% aggregate critical Stage 5 coverage.
- Alembic remains at `0005_invitation_email_outbox`; empty-database migration coverage passes,
  `current --check-heads` passes, and autogenerate reports no metadata drift.
- The five CRA-36 checkpoints are committed on `main` and fast-forward published through
  `de6dd84`. Canonical acceptance and push evidence remains in Linear/Git.

## Accepted CRA-38 Stage 6 checkpoint

- Adds `POST /api/v1/organizations/{organization_id}/employees/{employee_id}/activate` for an
  authenticated, MFA-verified same-Organization Admin with CSRF and a required trimmed
  `Idempotency-Key`.
- Locks the scoped EmployeeProfile and Membership, revalidates nonblank names and active
  same-Organization Role/Location references, then moves only Pending Membership to Active.
- The same transaction records `activated_at`, clears `disabled_at`, appends one PII-safe
  `employee_activated` audit, and reserves the existing API idempotency record. Failures roll back
  all three boundaries.
- Same-key replay creates no duplicate audit. Concurrent same-key requests converge on one result;
  concurrent different keys produce one success and one `EMPLOYEE_ACTIVATION_NOT_ALLOWED` conflict.
- Training participation is derived as Active. The explicit applicability call returns zero
  published content, assignments, and notifications; no placeholder data, job, provider call,
  schema object, or migration is added. Activation issues no new Session.
- Focused Stage 6 API/integration/security evidence: `21 passed / 0 failed / 0 skipped`; the final
  API-only activation/security subset reports `18 passed / 0 failed / 0 skipped`.
- Full candidate gate: Python 3.12.10, PostgreSQL 16, `211 passed / 0 failed / 0 skipped`, 94%
  overall branch coverage, and 92% coverage for `app/services/employees.py`. Ruff format/check and
  mypy pass.
- Alembic remains at `0005_invitation_email_outbox`; empty-database migration coverage,
  `current --check-heads`, and autogenerate no-drift checks pass.
- The accepted CRA-38 series is `0291208`, `e53e614`, `b0cd89b`, `c55545a`, and `bd2f98e`; it is
  published as part of the backend baseline through `abad74e`.

## Accepted CRA-40 Stage 7 checkpoint

- Adds one test-only complete backend acceptance chain: real Admin password login and MFA,
  Invitation create, persisted outbox and fake delivery capture, new-User acceptance, Pending
  restriction, Admin profile setup, explicit idempotent Activation, and Active access through the
  same employee Session.
- Adds a separate deny-by-default assertion for a Disabled Membership at the existing Active
  employee authorization guard.
- No production code, API contract, schema, migration, dependency, provider, worker, frontend, or
  `Photos/` change was required.
- Focused Stage 7 evidence: `2 passed / 0 failed / 0 skipped`. Adjacent auth, invitation, employee,
  security, delivery, and applicability evidence: `85 passed / 0 failed / 0 skipped`.
- Full candidate gate: Python 3.12.10, PostgreSQL 16, `213 passed / 0 failed / 0 skipped`, 94.05%
  exact overall statement/branch coverage, and 91.80% aggregate coverage across the declared
  17-file critical first-slice set. Ruff format/check and strict mypy pass.
- Alembic remains at `0005_invitation_email_outbox`; empty-database migration coverage,
  `current --check-heads`, and metadata no-drift checks pass.
- OpenAPI exposes 17 paths; all eight required first-slice paths are present and the forbidden
  `password_hash`, `token_hash`, `csrf_token_hash`, `secret_encrypted`, and `raw_token` fields are
  absent.
- The CRA-40 checkpoints are `a7c73df`, `2fd8254`, and `abad74e`; the accepted backend baseline is
  published on `origin/main` through `abad74e`.

## Current CRA-43 frontend candidate

- Adds the approved React 19/TypeScript/Vite/Tailwind toolchain with exact pinned dependencies and
  no global-state, form-schema, mock-server, animation, icon, or OpenAPI-generator dependency.
- Uses the accepted cookie session, CSRF, idempotency, MFA, invitation, Employee, and Activation
  contracts without changing the backend or persisting secrets in browser storage.
- Implements responsive Admin and Employee shells, login/MFA, invitation acceptance, Pending
  state, Admin invitation/profile setup, separate confirmed Activation, and truthful Active home.
- Vitest/Testing Library candidate: 13 passed, 0 failed, 0 skipped across nine files.
- Playwright candidate: 3 passed, 0 failed, 0 skipped at 1440×1000, 768×1024, and 375×812.
- The five implementation checkpoints are `5b7e637`, `0ea5f14`, `6bcc8c4`, `b1aa74b`, and
  `c5f38a8`; the sixth acceptance/documentation checkpoint is the current authorized boundary.

## Repository and runtime state

- Branch: `main`.
- Repository history includes the accepted backend MVP Vertical Slice 1 published through
  `abad74e`, plus the local CRA-43 frontend checkpoints on `main`.
- Git remote: `origin` points to the approved `GarnikSacsha/HorecaFam-` repository.
- Published branch: local `main` tracks `origin/main` at `abad74e`; the backend series was
  fast-forward published without force-push or history rewriting.
- Native PostgreSQL service: `postgresql-x64-16`, installed locally for the accepted test boundary.
- Local `backend/.env.test`: present and ignored; its values must never be printed or committed.
- Docker runtime: not installed or verified on this host; `compose.test.yml` remains supported.
- `frontend/`: active CRA-43 React implementation and automated acceptance boundary.

## Protected uncommitted material

- `Photos/` contains seven project-asset JPG files for
  [CRA-19 Bacara Welcome / homepage](https://linear.app/craftspacee/issue/CRA-19/design-bacara-welcome-brand-intro-responsive-mockups).
- These assets are deferred from the initial backend/docs baseline and remain untouched,
  unignored, and unstaged.
- Do not move, rename, optimize, delete, ignore, stage, commit, or publish them unless a separate
  bounded CRA-19 implementation/asset commit map explicitly authorizes those actions.
- Local environments, caches, coverage data, installers, and acceptance helpers are not baseline
  artifacts even when present on disk.

## Authority and next gates

- The currently active bounded task is always determined through Linear START HERE and the single
  active Linear issue, not through this snapshot.
- The accepted five-commit CRA-23 map was executed locally under the explicit CRA-25
  authorization and accepted by Denys. Its initial publication and repository-state synchronization
  are recorded in CRA-26. Further staging or commits require a new bounded map and explicit
  authorization.
- Every later push remains a separate approval gate, as do PR, merge, history rewrite, Railway,
  and deployment.
- CRA-28 local commit and initial publication were separately authorized by Denys; their exact Git
  evidence remains canonical in CRA-28. Later commits and pushes require new explicit approval.
- CRA-32, CRA-34, and CRA-36 are accepted, Done, and published; their canonical implementation and
  Git evidence remains in Linear.
- CRA-37 through CRA-41 are accepted and Done; the backend baseline through CRA-40 is published.
  CRA-43 is the active frontend implementation issue, and its six local commits are authorized.
  Candidate acceptance and every remote action remain separate gates. Push, PR, merge, deploy,
  providers, non-test mutations, architecture changes, migration, and history rewrite are not
  authorized by CRA-43.

Update this file after each accepted bounded issue or material repository/runtime change. Keep
product and contract decisions in Linear rather than copying them here.
