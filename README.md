# HoReCaFam

Repository for the HoReCa Training Platform. The accepted backend MVP Vertical Slice 1 through
CRA-40 is published on `origin/main` through `abad74e`. CRA-41 is the accepted frontend planning
checkpoint. CRA-43 is the active bounded implementation issue for Frontend MVP Vertical Slice 1;
its local six-checkpoint map is authorized, while push, PR, merge, deployment, and providers remain
separate gates. CRA-42 is an unrelated Backlog task and is not part of this sequence.

## Start here

- Agents: read [`AGENTS.md`](AGENTS.md) and [`.harness/START-HERE.md`](.harness/START-HERE.md).
- Current checkpoint: [`STATUS.md`](STATUS.md).
- Durable project context: [`CONTEXT.md`](CONTEXT.md).
- Canonical product source:
  [START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).

Linear remains canonical for product, API, data, RBAC, test-stage, scope, and approval decisions.
Repository documentation summarizes verified local state and routes agents to those sources.

## Repository map

- [`backend/`](backend): Python 3.12, FastAPI, SQLAlchemy 2, asyncpg, and Alembic-managed Stage 0–6
  backend foundations.
- [`frontend/`](frontend): React 19, TypeScript, Vite, Tailwind CSS, Vitest, Testing Library, and
  Playwright implementation for CRA-43.
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
remain outside the implemented backend boundary. Accepted CRA-36 adds MFA-scoped Organization
references and Employee list/detail reads, own read-only operational profiles, and CSRF-protected
Pending profile setup. Accepted CRA-38 adds explicit, idempotent Pending-to-Active
activation with locked reference revalidation, a safe audit, and an explicit zero-applicability
boundary. It creates no Session, Assignment, notification, content, provider call, or migration.
