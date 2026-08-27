# HoReCa Repository Status

**Snapshot date:** 2026-08-27
**Current bounded task:**
[CRA-34 — Implement Stage 4 Invitation Acceptance](https://linear.app/craftspacee/issue/CRA-34/implement-backend-mvp-vertical-slice-1-stage-4-invitation-acceptance),
routed through the Linear
[START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).
This document records durable checkpoints; it does not expand CRA-34 beyond its explicit approvals.

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
- CRA-32 Stage 3 invitation administration implementation is accepted and Done locally; its six
  commits are not yet published.
- CRA-33 Stage 4 invitation-acceptance plan is accepted and Done.
- CRA-34 Stage 4 invitation-acceptance implementation is a locally complete acceptance candidate.
  Its four authorized checkpoints are committed locally and are not yet accepted or published.
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

## Accepted local Stage 3 checkpoint

- CRA-32 implements the accepted invitation lifecycle boundary: persistence, transactional email
  outbox, deterministic versioned tokens, persistent idempotency and rate limits, create,
  validate, resend, and revoke.
- Accepted local gate: Python 3.12.10, PostgreSQL 16.15,
  `156 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 90% critical
  invitation coverage, Alembic head `0005_invitation_email_outbox`, and no metadata drift.
- Provider calls, a worker/runtime deployment, invitation acceptance, list/detail endpoints, and
  non-test provisioning remain outside CRA-32.
- Denys accepted CRA-32 on 2026-08-27. Linear records it as Done; publication remains a separate
  approval gate.

## Local Stage 4 acceptance candidate

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
- CRA-34 remains In Progress in Linear until Denys accepts this local candidate. Push remains a
  separate approval gate.

## Repository and runtime state

- Branch: `main`.
- Published history includes the accepted repository baseline, CRA-28 Stage 1, and CRA-30 Stage 2
  checkpoints. Local `main` adds six accepted CRA-32 checkpoints and four CRA-34 candidate
  checkpoints; none of those ten commits is published.
- Git remote: `origin` points to the approved `GarnikSacsha/HorecaFam-` repository.
- Published branch: local `main` tracks `origin/main`; the initial baseline was published without
  force-push or history rewriting.
- Native PostgreSQL service: `postgresql-x64-16`, installed locally for the accepted test boundary.
- Local `backend/.env.test`: present and ignored; its values must never be printed or committed.
- Docker runtime: not installed or verified on this host; `compose.test.yml` remains supported.
- `frontend/`: reserved boundary only.

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
- CRA-32 authorizes its six mapped local commits only. Push, PR, merge, deploy, Railway/provider
  provisioning, and history rewriting remain separate approval gates.
- CRA-33 accepted the Stage 4 contract and four-commit map. CRA-34 is the single bounded
  implementation issue, and Denys authorized all four selective local commits on 2026-08-27.
  Denys separately authorized production implementation on 2026-08-27. The local candidate now
  awaits acceptance. Push, PR, merge, deploy, providers, non-test mutations, dependencies,
  architecture changes, and history rewrite remain separate approval gates.

Update this file after each accepted bounded issue or material repository/runtime change. Keep
product and contract decisions in Linear rather than copying them here.
