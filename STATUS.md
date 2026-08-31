# HoReCa Repository Status

**Snapshot date:** 2026-08-31
**Published product implementation:** CRA-61 Interactive Training and CRA-62 synchronization are
accepted, Done and fast-forward published on `origin/main` through `c79db9d`. The canonical routing
entry is the Linear
[START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).
PR, merge, deployment, provider, and production-configuration actions remain separately gated.
CRA-42 is unrelated Backlog work.

**Current local boundary:** CRA-63 Practice planning and CRA-64 implementation are accepted and
Done. CRA-64 is the exact eight-checkpoint range `74c5741..cc1c05a`. CRA-65 is In Progress and
owns one selective documentation checkpoint plus one authorized ordinary non-force push. PR,
merge, deployment, provider calls and production actions remain separate gates.

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
- CRA-43 Frontend MVP Vertical Slice 1 implementation is accepted, Done, and published through
  `fa30a1f`.
- CRA-46 post-acceptance repository documentation synchronization is accepted, Done, and published
  through `586f8c5`.
- CRA-47 Menu Source of Truth planning and its ten-checkpoint implementation map are accepted and
  Done.
- CRA-48 published-baseline documentation synchronization is accepted, Done, and published. Its
  primary checkpoint is `3b95b3c`; the corrective publication record removes temporary pre-push
  wording, and no CRA-48 push remains pending.
- CRA-49 Menu Source of Truth implementation and corrective acceptance tail are accepted and
  published through `8028d6e`.
- CRA-53 Training Content planning and its nine-checkpoint implementation map are accepted and
  Done.
- CRA-54 Training Content is accepted, Done, and published through `d955f6a` as nine atomic
  checkpoints.
- CRA-55 post-CRA-54 documentation synchronization is Done.
- CRA-56 Slice 4 planning and its nine-checkpoint map are accepted and Done.
- CRA-57 Slice 4 implementation is accepted, Done, and published through `d4e0184`.
- CRA-58 is the documentation checkpoint that records CRA-57 acceptance and publication.
- CRA-60 Slice 5 planning and its nine-checkpoint implementation map are accepted and Done.
- CRA-61 Slice 5 Interactive Training is accepted and Done as `93ce970..614da3d`; CRA-62 owns its
  repository synchronization and publication evidence.
- CRA-62 is accepted, Done and published through `c79db9d`.
- CRA-63 Slice 6 Practice planning and its forty-scenario/eight-checkpoint map are accepted and Done.
- CRA-64 Slice 6 Practice is accepted and Done as `74c5741..cc1c05a`; CRA-65 owns documentation
  synchronization and ordinary publication.
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

## Accepted and published CRA-43 frontend checkpoint

- Adds the approved React 19/TypeScript/Vite/Tailwind toolchain with exact pinned dependencies and
  no global-state, form-schema, mock-server, animation, icon, or OpenAPI-generator dependency.
- Uses the accepted cookie session, CSRF, idempotency, MFA, invitation, Employee, and Activation
  contracts without changing the backend or persisting secrets in browser storage.
- Implements responsive Admin and Employee shells, login/MFA, invitation acceptance, Pending
  state, Admin invitation/profile setup, separate confirmed Activation, and truthful Active home.
- Vitest/Testing Library: 13 passed, 0 failed, 0 skipped across nine files.
- Playwright: 3 passed, 0 failed, 0 skipped at 1440×1000, 768×1024, and 375×812.
- The accepted series is `5b7e637`, `0ea5f14`, `6bcc8c4`, `b1aa74b`, `c5f38a8`, and `fa30a1f`.
  It was fast-forward published without history rewriting.

## Repository and runtime state

- Branch: `main`; `origin/main` is the accepted CRA-62 published baseline `c79db9d`. Local `main`
  contains the accepted CRA-64 eight-checkpoint range; CRA-65 owns its authorized publication.
- Repository history includes the accepted backend and frontend MVP Vertical Slice 1 checkpoints
  published through the CRA-43 endpoint `fa30a1f`, the accepted CRA-46/CRA-48 documentation
  checkpoints, CRA-49 through `8028d6e`, CRA-54 through `d955f6a`, CRA-55 through `afc607a`, and
  CRA-57 through `d4e0184`.
- Git remote: `origin` points to the approved `GarnikSacsha/HorecaFam-` repository.
- Published branch: CRA-49 and its corrective acceptance tail end at `8028d6e`; CRA-54's
  `8e15bd2..d955f6a`, CRA-55's `afc607a`, and CRA-57's `5823a0e..d4e0184` follow without force-push
  or history rewriting.
- Native PostgreSQL service: `postgresql-x64-16`, installed locally for the accepted test boundary.
- Local `backend/.env.test`: present and ignored; its values must never be printed or committed.
- Docker runtime: not installed or verified on this host; `compose.test.yml` remains supported.
- `frontend/`: accepted prior implementation plus the local CRA-64 Admin readiness and Employee
  Practice candidate.

## Accepted and published CRA-57 checkpoint

- Scope: version-owned audiences, shared applicability, immutable Assignment history, explicit
  Lesson Completion, derived current Progress, deterministic replacement-Version Rollout,
  transactional provider-free notification jobs, Admin assignment/rollout controls, and
  assignment-aware Employee Home/Learning.
- Backend gate: 363 passed, 0 failed, 0 skipped; 88% overall statement/branch coverage and 87%
  aggregate coverage across the seven Slice 4 service files; Ruff format/check and strict mypy
  passed.
- Migrations: accepted head `0009_assignment_completion_rollout`; empty-database upgrade,
  downgrade/upgrade coverage, current-head validation, and metadata no-drift passed.
- Frontend gate: Prettier, ESLint, TypeScript, and production build passed; Vitest reports 35
  passed, 0 failed, 0 skipped across 14 files.
- Browser gate: Playwright reports 12 passed, 0 failed, 0 skipped across 1440×1000, 768×1024,
  and 375×812 projects, including explicit Completion and Admin Assignment/Rollout confirmation.
- Exact evidence and limitations:
  [`docs/testing/training-assignment-slice-4-acceptance.md`](docs/testing/training-assignment-slice-4-acceptance.md).
- Denys explicitly accepted CRA-57; its nine-checkpoint range `5823a0e..d4e0184` was
  fast-forward published. No PR, merge, provider, deployment, or production configuration was
  performed.

## Accepted and published CRA-54 checkpoint

- Backend: 318 passed, 0 failed, 0 skipped on Python 3.12.10 and native PostgreSQL 16; 88% overall
  statement/branch coverage and 80% aggregate coverage across the predeclared seven-file critical
  Training set. Ruff format/check and strict mypy passed.
- Migrations: head `0008_training_content`; empty-database upgrade, Training migration round-trip,
  current-head validation, and metadata no-drift passed.
- Frontend: Prettier, ESLint, TypeScript, and production build passed; Vitest reports 27 passed,
  0 failed, 0 skipped across 14 files.
- Browser: Playwright reports 9 passed, 0 failed, 0 skipped across 1440×1000, 768×1024, and
  375×812 projects. The CRA-54 path covers Admin readiness/publication through Active Employee
  Module/Lesson reading.
- Scope: versioned Draft/Published Training content, seven strict block types, private images,
  atomic publication, and published-only Employee reference are implemented. Assignments,
  completions, progress, rollout, notifications, Practice, exams, and providers remain absent.
- Exact evidence and limitations:
  [`docs/testing/training-slice-3-acceptance.md`](docs/testing/training-slice-3-acceptance.md).
- Denys accepted CRA-54 and authorized fast-forward publication of the nine-checkpoint range
  `8e15bd2..d955f6a`. No Railway/provider smoke, PR, merge, deploy, or production configuration was
  performed.

## Accepted CRA-49 checkpoint and corrective closure

- Backend: 270 passed, 0 failed, 0 skipped on Python 3.12.10 and native PostgreSQL 16; 89% overall
  statement/branch coverage; Ruff format/check and strict mypy passed.
- Corrective RED → GREEN evidence: concurrent same-key Import Confirm reproduced `[200, 409]`
  in three of three runs, then returned replay-safe `[200, 200]` in three of three runs after a
  post-lock idempotency recheck. Different-key conflicts remain one-winner/one-conflict.
- Denys accepted the corrective coverage gate on 2026-08-28: at least 80% overall backend coverage
  with branch tracking, every mandatory Slice 2 scenario mapped, and explicit concurrency/security
  proof. No undeclared critical file set is selected retroactively.
- Migrations: head `0007_menu_import_review`; current-head, empty-database/round-trip coverage, and
  metadata no-drift passed.
- Frontend: Prettier, ESLint, TypeScript, and production build passed; Vitest reports 19 passed,
  0 failed, 0 skipped across 12 files.
- Browser: Playwright reports 6 passed, 0 failed, 0 skipped across desktop, compact, and mobile;
  the Menu path covers Admin JSON review/publication through Active Employee search/detail.
- Scope/security: Employee reads expose only the own Active Profile's current Published Menu;
  Training content, Assignments, and notifications remain zero-applicability; `Photos/` is
  untouched and unstaged.
- Exact matrix and limitations: [`docs/testing/menu-slice-2-acceptance.md`](docs/testing/menu-slice-2-acceptance.md).

## Accepted CRA-61 Interactive Training

- Scope: provenance-bound deterministic Question Candidates, Admin review/publication/readiness,
  immutable five-question Interactive Training Attempts, progressive idempotent Answers,
  immediate feedback, device takeover, Results, Latest/Best history, and responsive Admin/
  Employee UI.
- Backend gate: 424 passed, 0 failed, 0 skipped; 88% overall statement/branch coverage and 86%
  aggregate coverage across the predeclared five Slice 5 service files; Ruff and strict mypy pass.
- Migrations: head `0013_question_templates`; 13 migration tests, clean upgrade/current head and
  metadata no-drift pass. Active category, component, allergen and description rules are seeded by
  migrations.
- Frontend gate: Prettier, ESLint, TypeScript and production build pass; Vitest reports 45 tests;
  Playwright reports 15 executions across 1440×1000, 768×1024 and 375×812.
- Exact 27-scenario mapping and limitation:
  [`docs/testing/interactive-training-slice-5-acceptance.md`](docs/testing/interactive-training-slice-5-acceptance.md).
- Automated Candidate generation covers deterministic category/single-choice,
  components/multiple-choice, allergens/recognition and description/recognition templates from
  verified, unambiguous source facts. Ordering/assembly and matching templates are not generated
  because the current menu model does not prove preparation order or verified pair semantics.
- Denys explicitly accepted this evidence and its remaining source-bound limitation. The accepted
  range ends at `614da3d`; CRA-62 owns publication and exact remote evidence.

## Accepted CRA-64 Practice checkpoint

- Scope: Training-scoped `whole_menu_knowledge_check`, ten distinct Menu Items, final-only
  feedback, seven effective inactivity days with pause freeze/takeover, explicit atomic finish,
  Knowledge, critical-allergen evidence, durable Final Exam eligibility, Latest/Best/history,
  Admin readiness and Employee UI.
- Persistence head: `0014_practice_persistence`, including generic 5/10/20 assessment constraints
  and tenant-owned immutable eligibility.
- Source boundary: verified components, allergens and deterministic missing-component facts only;
  assembly/serving remains excluded without a structured approved source.
- Exact forty-scenario evidence and limitations:
  [`docs/testing/practice-slice-6-acceptance.md`](docs/testing/practice-slice-6-acceptance.md).
- Final Exam execution/certification, management Results, Attention/Retakes, providers,
  deployment and real Bacara ingestion remain absent.

## Remaining to a functional and pilot-ready MVP

Following accepted CRA-64, the functional product core still needs:

1. Slice 7 Final Exam and canonical Results: about 5–8 focused engineering days.
2. Slice 8 Attention and Retakes: about 4–6 focused days.
3. Pilot-critical access/admin/content closure: about 5–9 focused days, including elevated-user
   recovery/enrollment, Employee lifecycle administration, minimum venue setup, validated Bacara
   content and the complete synthetic end-to-end chain.

That leaves approximately 14–23 focused engineering days, or roughly 3–5 calendar weeks at the
current approval/checkpoint rhythm, to a local functional MVP. Pilot infrastructure, provider,
observability, backup/security/performance hardening and real-venue UAT add roughly 10–20 focused
days plus external latency. The credible pilot-ready window is therefore still about 5–9 calendar
weeks after CRA-64 acceptance; real verified content and external approvals are the largest risks.

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
- The active bounded repository issue is CRA-65. CRA-19 remains a separate visual-only track.
- CRA-65 authorizes only documentation synchronization, one selective local checkpoint and one
  ordinary non-force push with remote verification. Slice 7 requires a separate planning issue.
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
- CRA-37 through CRA-48 are accepted and Done. The CRA-43 implementation series ends at `fa30a1f`,
  and the published repository baseline includes the CRA-46 documentation checkpoint at `586f8c5`.
  CRA-48 and CRA-49 are accepted and published; the CRA-49 corrective endpoint is `8028d6e`.
  CRA-53 planning and CRA-54 implementation are accepted and Done; CRA-54 is published through
  `d955f6a`, and CRA-55 follows at `afc607a`. CRA-56 and CRA-57 are accepted and Done; CRA-57 is
  published through `d4e0184`, with CRA-58 providing this documentation checkpoint. Every later
  implementation, push, PR, merge, deploy, provider call, non-test mutation, production
  configuration, and history rewrite remains separately gated.

Update this file after each accepted bounded issue or material repository/runtime change. Keep
product and contract decisions in Linear rather than copying them here.
