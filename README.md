# HoReCaFam

Repository for the HoReCa Training Platform. The published accepted baseline through CRA-74 ends
at `4019262` and includes CRA-71 Attention and Retakes. CRA-77 Operations and Hardening has passed
fresh local acceptance as the complete thirteen-checkpoint range `974feeb..ef74be4` at Alembic head
`0018_job_runtime` and is accepted and Done in Linear. Publication remains pending. Its exact local
evidence and remaining pilot gates are in
[`docs/testing/operations-hardening-slice-9-acceptance.md`](docs/testing/operations-hardening-slice-9-acceptance.md).
CRA-119 Deployment and Provider Readiness now has a complete seven-checkpoint local candidate with
API/worker containers, async idempotent Resend adapters, Caddy delivery, and an unapplied Railway
topology. It awaits Denys acceptance; exact evidence and limitations are in
[`docs/testing/deployment-provider-readiness-cra-119.md`](docs/testing/deployment-provider-readiness-cra-119.md).
Push, PR, merge, deployment, provider calls, production configuration and non-test bootstrap remain
separate approval gates; CRA-42 is unrelated Backlog work.

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
  the locally accepted CRA-77 range is at head `0018_job_runtime`.
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

The CRA-119 candidate defines the production process boundaries without applying them: Uvicorn API,
durable Job worker, Caddy SPA/API proxy, managed PostgreSQL reference, private object-storage
configuration, and Resend delivery. Its final local gate reports 544 backend tests and 72 Vitest
tests with no failures or skips. Docker image smoke, Railway plan/apply, provider calls, backup/
restore, staging load, and venue UAT remain external gates.
