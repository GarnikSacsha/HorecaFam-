# Current Architecture

This document describes only the verified accepted implementation. Canonical future behavior and
contracts remain in Linear.

## Stage 0 runtime path

```text
FastAPI application factory
→ request ID middleware
→ unified exception handlers
→ /api/v1 router
→ GET /health
```

- `backend/app/main.py` creates the application and wires middleware, handlers, and the API router.
- `backend/app/api/router.py` owns the `/api/v1` prefix.
- `backend/app/api/routes/health.py` implements the accepted health boundary.
- `backend/app/core/request_id.py` creates or preserves a valid request ID and correlates safe
  internal-error handling.
- `backend/app/core/errors.py` owns the unified API error envelope.

Exact response shapes, localized messages, error codes, and future endpoints are canonical in
[CRA-12](https://linear.app/craftspacee/issue/CRA-12/define-rest-api-contract-and-pydantic-schemas),
not in this summary.

## Configuration and persistence boundary

```text
required environment configuration
→ async PostgreSQL engine
→ async session factory
→ explicit Alembic migrations
```

- `backend/app/core/config.py` requires an environment and an async PostgreSQL URL.
- `backend/app/db/session.py` creates the SQLAlchemy async engine/session boundary.
- `backend/app/db/safety.py` fails closed unless destructive test work targets `APP_ENV=test` and
  an explicitly test-scoped database.
- `backend/migrations/env.py` uses the runtime database URL when supplied and otherwise retains an
  invalid fail-closed placeholder.
- `backend/migrations/versions/0001_stage0_empty_schema.py` establishes Alembic history without
  domain tables.

The current data design, future models, migration order, and RBAC remain canonical in
[CRA-10](https://linear.app/craftspacee/issue/CRA-10/design-database-schema-and-entity-relationships).

## Test boundary

API tests run in-process through HTTPX ASGITransport. Persistence and migration tests require a
real dedicated PostgreSQL 16 database. See [`../testing/README.md`](../testing/README.md) and
[`../../.harness/TESTING.md`](../../.harness/TESTING.md).

## Explicitly absent

There are no domain tables, identity models, auth/session/CSRF/MFA implementation, invitations,
employee lifecycle, menu/training workflows, provider integrations, production resources, or
frontend application. Adding any of these requires a new bounded Linear issue and approval.
