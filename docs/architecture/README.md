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
- `backend/app/db/base.py` owns the shared SQLAlchemy metadata and deterministic naming convention.
- `backend/app/models` defines the seven CRA-28 identity entities, CRA-30 authentication/access
  state, and CRA-32 invitation, idempotency, rate-limit, background-job, and email-delivery state.
- `backend/migrations/env.py` wires that metadata into Alembic.
- `backend/migrations/versions/0001_stage0_empty_schema.py` establishes the base history;
  `0002_identity_persistence.py` creates Stage 1; `0003_auth_security.py` creates Stage 2;
  `0004_invitation_lifecycle.py` and `0005_invitation_email_outbox.py` create the local Stage 3
  candidate schema.
- Composite PostgreSQL foreign keys prevent EmployeeProfile role/location references from crossing
  organization boundaries. Membership states are limited to Pending, Active, and Disabled.

The current data design, future models, migration order, and RBAC remain canonical in
[CRA-10](https://linear.app/craftspacee/issue/CRA-10/design-database-schema-and-entity-relationships).

## Stage 2 authentication boundary

```text
password login → ordinary Session or one-time MFA challenge
MFA challenge + TOTP → elevated Session
Session cookie + synchronizer token → protected mutation
Session + scoped access state → deny-by-default RBAC dependency
```

Only `/api/v1/auth/login`, `/api/v1/auth/mfa/verify`, `/api/v1/auth/session`, and
`/api/v1/auth/logout` are production Stage 2 auth routes. Organization/Admin behavior is exposed
only as reusable dependencies and tested through test-only probes; no later-stage product route is
pulled forward.

## Stage 3 invitation boundary

```text
Admin + MFA + CSRF + idempotency key → create/resend invitation
public token body → validate invitation capability
Admin + MFA + CSRF → revoke invitation
business transaction → invitation + audit + background job + email delivery state
worker boundary → reconstruct current raw token only at the delivery adapter call
```

The accepted CRA-32 checkpoint exposes create, validate, resend, and revoke. Tokens are
deterministically derived from server-held ordered HMAC keys and versioned invitation identity;
only hashes and derivation coordinates persist. Delivery state is transactional, but no provider
call or deployed worker is included.

## Stage 4 invitation-acceptance boundary

```text
public invitation token + discriminated account mode
→ locked Invitation and global-email serialization
→ create or authenticate User
→ Pending Membership + placeholder EmployeeProfile
→ accepted Invitation + opaque Session + safe audit in one transaction
→ Secure HttpOnly cookie after commit
```

Accepted CRA-34 adds only `POST /api/v1/invitations/accept`. Invitation email and
Organization remain authoritative; the request cannot redirect identity or tenant ownership.
Concurrent reuse has one winner, all failures roll back, and the issued Session grants only the
existing Pending boundary. Acceptance never activates Membership, assigns Role/Location, or marks
MFA verified. No schema or migration was added.

## Stage 5 Pending/Admin Profile Setup boundary

```text
Admin Session + MFA + Organization scope → safe references and Employee reads
Admin Session + MFA + CSRF + Pending EmployeeProfile → normalized profile replacement
active same-Organization Role/Location + locked transaction → profile + safe audit commit
Employee Session → own read-only operational profiles
```

Accepted CRA-36 exposes Organization summary, Location/OperationalRole references,
cursor-paginated Employee list/detail, own `/me/profile`, and Pending-only Employee PATCH.
EmployeeProfile ID is the public Employee identifier. Tenant filters precede object filters,
cross-Organization probes do not enumerate resources, and completeness is derived from nonblank
names plus active same-Organization Role/Location. No schema/migration, Activation, Assignment,
Training, notification, provider, worker, or frontend behavior is added.

## Test boundary

API tests run in-process through HTTPX ASGITransport. Persistence and migration tests require a
real dedicated PostgreSQL 16 database. See [`../testing/README.md`](../testing/README.md) and
[`../../.harness/TESTING.md`](../../.harness/TESTING.md).

## Explicitly absent

There is no invitation list/detail workflow, password recovery, MFA enrollment, Organization or
reference CRUD, Employee Activation/lifecycle administration, menu/training workflow, provider
integration, deployed worker/resource, or frontend application. Adding any of these requires a
new bounded Linear issue and approval.
