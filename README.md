# HoReCaFam

HoReCa Training Platform for Bacara: Admin content and employee learning.

Current progress, source versions and next acceptance steps: [STATUS](STATUS.md).
Use that single checkpoint for delivered versions, content readiness and the next user journey.
Detailed implementation and delivery evidence is indexed in [testing](docs/testing/README.md).
The [September 21 reconciliation](docs/testing/reconciliation-2026-09-21.md) separates published
source, delivered fixes, completed local checkpoints and remaining owner acceptance.

## Start here

- Agents: read [`AGENTS.md`](AGENTS.md) and [`.harness/START-HERE.md`](.harness/START-HERE.md).
- Current checkpoint: [`STATUS.md`](STATUS.md).
- Durable project context: [`CONTEXT.md`](CONTEXT.md).
- Canonical product source:
  [START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).

Linear remains canonical for product, API, data, RBAC, test-stage, scope, and approval decisions.
Repository documentation summarizes verified local state and routes agents to those sources.

## Repository map

- [`backend/`](backend): Python 3.12, FastAPI, SQLAlchemy 2, asyncpg, and Alembic-managed runtime;
  the current published schema head is `0020_menu_change_history`.
- [`frontend/`](frontend): React 19, TypeScript, Vite, Tailwind CSS, Vitest, Testing Library, and
  Playwright, including local CRA-77 security, lifecycle, audit and operator interfaces.
- [`docs/architecture/`](docs/architecture): verified implementation architecture.
- [`docs/decisions/`](docs/decisions): repository-local engineering decision index.
- [`docs/testing/`](docs/testing): test structure and accepted evidence.
- `Photos/`: project assets for
  [CRA-19 Bacara Welcome / homepage](https://linear.app/craftspacee/issue/CRA-19/design-bacara-welcome-brand-intro-responsive-mockups),
  deferred from the initial backend/docs baseline. Moving, renaming, optimizing, staging, or
  publishing them requires a separate bounded CRA-19 implementation/asset commit map.


## Working commands

Use [.harness/TESTING.md](.harness/TESTING.md) for the supported runtime, safe test environment
and exact commands. The dated construction and delivery notes below are historical only.

<details>
<summary>Historical checkpoints — not current instructions</summary>


## Current staging state — after API rollout, 2026-09-11

Follow the [verified staging checkpoint](STATUS.md#verified-staging-checkpoint--2026-09-11-after-api-rollout).
CRA-171 is committed at `0956e7b`; migration and runtime grants completed in the preceding task,
and API/web are running. Worker, account setup and authenticated acceptance remain open.
The earlier snapshot below is historical and must not drive repeated migration or setup actions.

## Earlier current checkpoint — 2026-09-11, before migration/API rollout

The local demo implementation is committed through `ede4281` (16 checkpoints ahead of
GitHub `fafec73`, behind 0; direct remote read September 11). The exact ledger and recorded
September 10 verification are in [the candidate report](docs/testing/demo-candidate-2026-09-10.md).
Recorded final gates: 865 backend, 89 Vitest and 69 Playwright passed, zero failures/errors/skips;
93.96% statements, 80.46% branches and 89.77% fixed critical aggregate. These are not new test runs.

Denys accepted CRA-131's current public-page visual iteration on September 11; copy refinement
and additional animation are deferred. CRA-123–126 remain accepted and Done. Other local
implementation acceptance remains distinct from completed commits and staging delivery.

The accepted account direction is protected one-time provisioning of a separate technical
operator and Alexandra's Organization Admin account. Alexandra uses existing email invitations
for employees. An owner provisioning cabinet is deferred. No new operational role is implied.

Fresh September 11 Railway read: PostgreSQL has one active successful deployment; nine application
services have no source or deployment; five cron schedules are null. Pending settings count is
unavailable. Selected staging SHA remains `fafec73`; replacement selection and rollout are separate.
No application code, Git index, commit, push, deployment or non-test data changed in this
documentation synchronization. Older current-state wording below is historical where superseded.

## Current local checkpoint — 2026-09-09

Public entry, Employee profile, expanded Practice, other-device logout and Admin Dashboard
are local implementation candidates. See [STATUS](STATUS.md) for their acceptance boundaries,
[current verification](docs/testing/README.md) for final test evidence, and the
[staging runbook](docs/deployment/staging-acceptance-cra-122.md) for remaining delivery/account gates.
The selected staging SHA below predates these uncommitted changes. Linear START HERE and the
two-person demo document are synchronized to this checkpoint; no release is implied.

## Accepted decision — 2026-09-08

Denys explicitly confirmed the reviewed acceptance packet: CRA-123, CRA-124, CRA-125 and
CRA-126 are formally accepted with their recorded verification limits and marked Done in Linear.
The selected candidate for all nine staging application services is
`fafec73ad7f3438e1b545acea7cde3018b7f2fbf`, with schema
`0019_auth_security_budgets`, replacing `2275cee1ae46da708f33a032229e708c73a966c8`.

This decision supersedes earlier pending-acceptance and proposed-candidate wording below.
The reviewed migration/recovery/storage limits remain applicable. CRA-122 stays In Progress:
real staging acceptance has not run. Source binding, archive delivery, provider changes,
non-test migration, deployment, commits and push are not authorized by this acceptance.
The local source-binding draft now names the selected SHA for all nine services; it is not applied.
Next: resolve the supported delivery mechanism and prepare the remaining concrete prerequisites.

Repository for the HoReCa Training Platform.

Published `main` is `fafec73ad7f3438e1b545acea7cde3018b7f2fbf` (CRA-123/124/125/126 included).
The direct GitHub ref, local main and origin/main match. CRA-126 records 832 backend tests
passed with zero failures/errors/skips; independent statements 93.86%, branches 80.19% and
critical aggregate 89.67% pass. Source migration head: `0019_auth_security_budgets`.
Formal acceptance of CRA-123/124/125/126 remains open.

CRA-122 owns current synchronization and staging preparation. The last accepted staging SHA
is `2275cee1ae46da708f33a032229e708c73a966c8`; `fafec73` is only a proposed replacement.
Build/start settings and cron suspension were recorded as applied on September 7; source binding
and application rollout remain unperformed in the latest evidence. Autodeploy suppression at
binding time, migration/rollback and real provider acceptance are still open. No live provider
check or application suite was rerun by this synchronization.

Use [STATUS.md](STATUS.md) for the current checkpoint and dated evidence, and the
[staging preparation](docs/deployment/staging-cra-122.md) for exact remaining gates.
CRA-19 remains a separate visual track. Commit, push, deployment and non-test data are not
authorized by documentation synchronization.

## Start here

- Agents: read [`AGENTS.md`](AGENTS.md) and [`.harness/START-HERE.md`](.harness/START-HERE.md).
- Current checkpoint: [`STATUS.md`](STATUS.md).
- Durable project context: [`CONTEXT.md`](CONTEXT.md).
- Canonical product source:
  [START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).

Linear remains canonical for product, API, data, RBAC, test-stage, scope, and approval decisions.
Repository documentation summarizes verified local state and routes agents to those sources.

## Repository map

- [`backend/`](backend): Python 3.12, FastAPI, SQLAlchemy 2, asyncpg, and Alembic-managed runtime;
  the current published source head is `0019_auth_security_budgets`.
- [`frontend/`](frontend): React 19, TypeScript, Vite, Tailwind CSS, Vitest, Testing Library, and
  Playwright, including local CRA-77 security, lifecycle, audit and operator interfaces.
- [`docs/architecture/`](docs/architecture): verified implementation architecture.
- [`docs/decisions/`](docs/decisions): repository-local engineering decision index.
- [`docs/testing/`](docs/testing): test structure and accepted evidence.
- `Photos/`: project assets for
  [CRA-19 Bacara Welcome / homepage](https://linear.app/craftspacee/issue/CRA-19/design-bacara-welcome-brand-intro-responsive-mockups),
  deferred from the initial backend/docs baseline. Moving, renaming, optimizing, staging, or
  publishing them requires a separate bounded CRA-19 implementation/asset commit map.

## Local development

Create the approved Python environment from the repository root:

```powershell
rtk py -3.12 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
```

Read [`backend/AGENTS.md`](backend/AGENTS.md) before backend work and use the exact quality/test
commands in [`.harness/TESTING.md`](.harness/TESTING.md). Real PostgreSQL 16 is required for
integration and migration acceptance; there is no SQLite fallback. Frontend setup and commands
are documented in [`frontend/README.md`](frontend/README.md).

Stage 1 persists identity and organization records. Accepted CRA-30 adds non-enumerating
login, server-side sessions, CSRF-protected logout, TOTP completion, and Organization-scoped RBAC
dependencies. Accepted CRA-32 adds create, public validate, resend, and revoke invitation flows
backed by persistent idempotency/rate limits and a transactional email outbox. Accepted CRA-34
adds atomic new/existing-account invitation acceptance, Pending access, an opaque Session, and
safe cookie/audit integration. Provider/worker execution, invitation list/detail
endpoints, MFA enrollment/recovery, training workflows, and broader production administration
remain outside the first-slice backend boundary. Accepted CRA-36 adds MFA-scoped Organization
references and Employee list/detail reads, own read-only operational profiles, and CSRF-protected
Pending profile setup. Accepted CRA-38 adds explicit, idempotent Pending-to-Active
activation with locked reference revalidation, a safe audit, and an explicit zero-applicability
boundary. It creates no Session, Assignment, notification, content, provider call, or migration.
Accepted CRA-49 adds Location-owned versioned Menu persistence, guarded Draft/import/
publication administration, and a published-only Active Employee reference UI. Its fresh evidence
is recorded in [`docs/testing/menu-slice-2-acceptance.md`](docs/testing/menu-slice-2-acceptance.md).
Accepted CRA-54 adds Location-owned versioned Training Drafts, seven strict lesson block
types, private images, readiness and atomic publication, an Admin authoring workspace, and a
published-only Active Employee editorial reader. Assignments, completions, progress, Practice,
notifications, providers, and deployment remain outside Slice 3. Accepted evidence is in
[`docs/testing/training-slice-3-acceptance.md`](docs/testing/training-slice-3-acceptance.md).
Accepted CRA-57 adds version audiences, immutable Assignment history, explicit Lesson
Completion, derived Progress, deterministic replacement-Version Rollout, Admin assignment/rollout
controls, and assignment-aware Employee Learning. Its executed evidence is recorded in
[`docs/testing/training-assignment-slice-4-acceptance.md`](docs/testing/training-assignment-slice-4-acceptance.md);
the accepted nine-checkpoint range ends at `d4e0184`.

Accepted CRA-61 adds deterministic provenance-bound category, component, allergen and
description Question Candidates, Admin human review and readiness, immutable five-question
Interactive Training Attempts, progressive Answers with immediate feedback, device takeover,
Results and Latest/Best history, plus responsive Admin and Employee UI. Its accepted evidence is
recorded in
[`docs/testing/interactive-training-slice-5-acceptance.md`](docs/testing/interactive-training-slice-5-acceptance.md).
The accepted range ends at `614da3d`; CRA-62 governs repository synchronization and publication.
Accepted CRA-64 adds Training-scoped ten-Question Practice with final-only feedback,
durable Final Exam eligibility, Admin readiness and Employee UI. Its executed evidence is recorded
in [`docs/testing/practice-slice-6-acceptance.md`](docs/testing/practice-slice-6-acceptance.md).
The accepted range ends at `cc1c05a`, and CRA-65 publishes its synchronization checkpoint through
`4164b9c`. Accepted CRA-67 adds 20-question Final Exam execution, final-only feedback,
exact 70% passing, certification, failed-attempt immediate retake, and canonical Admin Results.
Its evidence is in
[`docs/testing/final-exam-slice-7-acceptance.md`](docs/testing/final-exam-slice-7-acceptance.md).
The accepted CRA-71 implementation adds Attention/Retakes administration and Employee
follow-up behavior;
its exact evidence is in
[`docs/testing/attention-retakes-slice-8-acceptance.md`](docs/testing/attention-retakes-slice-8-acceptance.md).
The locally accepted CRA-77 range adds recovery/MFA enrollment, Employee lifecycle controls, durable
workers and maintenance, audit/operator tooling, structured observability and dry-run-first venue
bootstrap. Its final local gate reports 530 backend tests at 86% overall coverage, 81% aggregate
critical-set coverage, 72 Vitest tests and 42 Playwright executions. Providers, non-test bootstrap
apply, deployment, backup restore, staging load and real-venue UAT remain outside the verified
local boundary. Its provider, restore, rollback and physical-UAT gates are itemized in
[`docs/testing/operations-hardening-slice-9-release-checklists.md`](docs/testing/operations-hardening-slice-9-release-checklists.md).

The accepted and published CRA-119 range defines the production process boundaries without applying
them: Uvicorn API,
durable Job worker, Caddy SPA/API proxy, managed PostgreSQL reference, private object-storage
configuration, and Resend delivery. Its final local gate reports 544 backend tests and 72 Vitest
tests with no failures or skips. Docker image smoke, Railway plan/apply, provider calls, backup/
restore, staging load, and venue UAT remain external gates.

</details>
