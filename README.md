# HoReCaFam

Repository for the HoReCa Training Platform. The published accepted implementation contains the
CRA-20 Stage 0 FastAPI foundation and CRA-28 Stage 1 identity persistence. CRA-30 adds a locally
verified Stage 2 authentication/security candidate pending final acceptance and publication.

## Start here

- Agents: read [`AGENTS.md`](AGENTS.md) and [`.harness/START-HERE.md`](.harness/START-HERE.md).
- Current checkpoint: [`STATUS.md`](STATUS.md).
- Durable project context: [`CONTEXT.md`](CONTEXT.md).
- Canonical product source:
  [START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).

Linear remains canonical for product, API, data, RBAC, test-stage, scope, and approval decisions.
Repository documentation summarizes verified local state and routes agents to those sources.

## Repository map

- [`backend/`](backend): Python 3.12, FastAPI, SQLAlchemy 2, asyncpg, and Alembic-managed Stage 0–2
  backend foundations.
- [`frontend/`](frontend): reserved boundary for a separately approved frontend stage.
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
integration and migration acceptance; there is no SQLite fallback.

Stage 1 persists identity and organization records. The CRA-30 candidate adds non-enumerating
login, server-side sessions, CSRF-protected logout, TOTP completion, and Organization-scoped RBAC
dependencies. Invitations, MFA enrollment/recovery, training workflows, production admin
endpoints, and the frontend application remain outside the implemented boundary.
