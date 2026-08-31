# HoReCaFam

Repository for the HoReCa Training Platform. Backend MVP Vertical Slice 1 through CRA-40 and
Frontend MVP Vertical Slice 1 through CRA-43 are accepted, Done, and fast-forward published on
`origin/main`; the CRA-43 implementation series ends at `fa30a1f`, while the accepted CRA-46
documentation publication advances the published `origin/main` baseline to `586f8c5`. CRA-47
planning for Menu Slice 2 is accepted and Done. The CRA-48 documentation checkpoint `3b95b3c` and
its corrective publication record are published; CRA-48 is Done. CRA-49 Menu Source of Truth is
accepted and fast-forward published on `origin/main` through corrective checkpoint `8028d6e`.
CRA-53 Training Content planning and CRA-54 implementation are accepted and Done; CRA-54 is
published through `d955f6a`, and CRA-55 advances the prior documentation baseline to `afc607a`.
CRA-56 Slice 4 planning and CRA-57 Assignment, Completion, Progress and Rollout implementation are
accepted and Done. The nine CRA-57 checkpoints are fast-forward published through `d4e0184`; the
CRA-58 documentation checkpoint follows that range. CRA-60 Slice 5 planning is accepted and Done.
CRA-61 Interactive Training is accepted and Done as the eleven-commit local range
`93ce970..614da3d`. CRA-62 is the bounded synchronization/publication checkpoint for that accepted
range; exact remote publication evidence is recorded in Linear. CRA-63 Practice planning and
CRA-64 Practice are accepted and Done as the exact eight-commit range `74c5741..cc1c05a`; CRA-65
synchronization is published through `4164b9c`. CRA-66 Final Exam planning and CRA-67 Final Exam/
canonical Results are accepted and Done; CRA-67 is the exact eight-checkpoint range
`6be8f4d..703872b`. CRA-68 is the active synchronization/publication checkpoint. Push beyond that
authorization, PR, merge, deployment, providers, and production configuration remain separate
gates. CRA-42 is unrelated Backlog work.

## Start here

- Agents: read [`AGENTS.md`](AGENTS.md) and [`.harness/START-HERE.md`](.harness/START-HERE.md).
- Current checkpoint: [`STATUS.md`](STATUS.md).
- Durable project context: [`CONTEXT.md`](CONTEXT.md).
- Canonical product source:
  [START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).

Linear remains canonical for product, API, data, RBAC, test-stage, scope, and approval decisions.
Repository documentation summarizes verified local state and routes agents to those sources.

## Repository map

- [`backend/`](backend): Python 3.12, FastAPI, SQLAlchemy 2, asyncpg, Alembic-managed accepted
  runtime through accepted CRA-67 Final Exam and Results.
- [`frontend/`](frontend): React 19, TypeScript, Vite, Tailwind CSS, Vitest, Testing Library, and
  Playwright through accepted CRA-67 Final Exam and Results.
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
Attention/Retakes administration, providers and deployment remain outside the local boundary.
