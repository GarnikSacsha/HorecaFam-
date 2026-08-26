# HoReCa Repository Status

**Snapshot date:** 2026-08-26
**Current bounded task:** resolve through the Linear
[START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974)
and the single active Linear issue. This document records durable checkpoints; it does not select
or authorize the current task.

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
- CRA-30 implements the locally verified Stage 2 authentication/session/CSRF/MFA/RBAC candidate.
- Current local gate: Python 3.12.10, PostgreSQL 16.15, `91 passed / 0 failed / 0 skipped`, 94%
  overall statement/branch coverage, 92% critical auth coverage, Alembic head
  `0003_auth_security`, and no metadata drift.
- CRA-30 remains In Progress until Denys's final acceptance; its local commits are not yet
  published.

## Repository and runtime state

- Branch: `main`.
- Published history includes the accepted repository baseline and CRA-28 Stage 1 checkpoint;
  CRA-30 adds five local Stage 2 checkpoints pending acceptance/publication.
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
- CRA-30 authorizes its mapped local commits only. Push, Stage 3, PR, merge, deploy, Railway, and
  history rewriting remain separate approval gates.

Update this file after each accepted bounded issue or material repository/runtime change. Keep
product and contract decisions in Linear rather than copying them here.
