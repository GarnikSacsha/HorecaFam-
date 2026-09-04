# CRA-119 accepted deployment and provider readiness evidence

**Evidence date:** 2026-09-02
**Bounded issue:** [CRA-119](https://linear.app/craftspacee/issue/CRA-119/implement-deployment-and-provider-readiness)
**Repository base:** `c8a11359318757fecffa18ea7f2bc120ebc2a842`
**Published endpoint:** `2644b796b122b9d160392f8e95cc515e736f7de9`
**Acceptance state:** accepted, Done, and fast-forward published on 2026-09-02

## Implemented boundary

CRA-119 turns the accepted CRA-77 application into a repository-defined deployment artifact
without creating or changing external infrastructure. The seven authorized checkpoints are:

1. a fail-closed API/worker environment contract and a secret-safe variable inventory;
2. an ASGI API entry point plus an unprivileged backend container image;
3. one production worker composition containing every approved durable Job handler;
4. async Resend adapters for invitation and password-reset email with Job-derived idempotency;
5. an unprivileged Caddy frontend image with SPA fallback and same-origin `/api` proxying;
6. a pinned Railway Infrastructure-as-Code topology for PostgreSQL, API, worker, and web;
7. this integrated readiness record and repository-state synchronization.

The implementation checkpoints preceding this record are:

| Checkpoint | Outcome |
| --- | --- |
| `b1d145b` | Runtime environment contract |
| `8a5c51a` | API entry point and backend container |
| `6bce3cb` | Worker composition and in-product adapter |
| `a823d4d` | Idempotent Resend adapters |
| `b2a3e0e` | Frontend Caddy image |
| `915af8e` | Railway project topology |
| `2644b79` | Integrated readiness evidence and repository-state record |

The exact seven-checkpoint range `b1d145b..2644b79` was accepted and fast-forward published without
a merge commit or history rewrite. Publication did not apply the Railway topology or call a provider.

## Runtime topology and contract impact

- The API starts with `python -m app.api_server`, using Uvicorn factory `app.main:create_app`, and disposes its async SQLAlchemy engine during
  lifespan shutdown.
- The worker runs `python -m app.worker`, uses the existing durable Job lease/heartbeat runtime,
  and registers invitation, password-reset, training-notification, maintenance, and audit handlers.
- Resend receives no durable application secret or raw token in Job payloads. Invitation and reset
  links are derived at delivery time, and the stable Job identifier is sent as the provider
  idempotency key.
- Caddy serves the built React SPA on port `8080`, sends `/api` to the private API service, and
  retains the client-side route fallback.
- Railway desired state declares managed PostgreSQL and separate API, worker, and web services.
  Secret values remain provider-owned through `preserve()` and are not present in Git.
- Railway-style `postgresql://` and `postgres://` URLs are normalized to SQLAlchemy's asyncpg
  driver form inside backend configuration.

There is no new HTTP endpoint, OpenAPI field, database object, migration, or browser-visible
provider secret. Sentry is deliberately excluded: no dependency, SDK initialization, DSN, or
provider configuration was added.

The complete environment inventory is in
[`../deployment/environment.md`](../deployment/environment.md), and the unapplied Railway workflow
is in [`../../.railway/README.md`](../../.railway/README.md).

## Executed evidence

### Backend

- Python 3.12.10 with the dedicated real PostgreSQL 16 test boundary.
- Ruff format check: 235 files already formatted.
- Ruff check: passed.
- Strict mypy across `app` and `tests`: passed for 214 source files.
- Full pytest gate: **544 passed / 0 failed / 0 skipped** in 20 minutes 41 seconds.
- Overall statement/branch coverage: **86%**.
- Alembic current head: `0018_job_runtime`.
- Alembic metadata drift check: no new upgrade operations detected.
- Focused Resend/worker real-PostgreSQL integration: 12 passed.

The first full API subset exposed one stale fixed test timestamp in the elevated-password-change
fixture. Its session was dated before the current server-generated creation time and correctly
violated the database expiry constraint. The fixture now uses the current UTC test clock; the
focused regression reports 1 passed, the adjacent login/MFA set reports 13 passed, and the final
full gate above is green.

### Frontend and deployment artifacts

- Prettier, ESLint, TypeScript, and the Vite production build passed.
- Full Vitest: **72 passed / 0 failed / 0 skipped** across 21 files.
- Static frontend container/Caddy contract: 2 passed.
- Railway topology TypeScript check: passed.
- Railway topology static contract: **3 passed / 0 failed / 0 skipped**.

The production frontend build contains 67 transformed modules. No build-time backend URL or
provider secret is required because browser traffic uses same-origin `/api`.

## Security and operations review

- Real credentials remain absent from tracked files; `.env.example` contains names and safe
  placeholders only.
- API and web images use unprivileged runtime users.
- The worker refuses production startup when its identity, public URL, provider credential, sender,
  or required cryptographic settings are missing.
- Provider idempotency is stable across retries, while durable delivery state remains authoritative
  in PostgreSQL.
- API, worker, and web are separate deployable processes; the worker is not hidden inside an API
  process and no second scheduler/runtime was introduced.
- Database migration remains an explicit one-off release action before traffic is switched.

## Unperformed gates and limitations

These items are **not** passing evidence and remain separately authorized external work:

- Docker image builds and container smoke tests. Docker CLI 29.7.2 was present, but the local
  Docker Desktop Linux engine was unavailable, so neither image was built locally.
- Railway project linking, `railway config plan`, `railway config apply`, service provisioning,
  domain assignment, variables, migration execution, deploy, healthcheck, or rollback smoke.
- A real Resend send, sender/domain verification, invitation/reset receipt, duplicate-suppression,
  bounce, or provider-failure exercise.
- Private object-storage provisioning and live upload/download proof.
- Backup retention configuration and isolated restore proof.
- Staging load/performance evidence, real Bacara content validation, physical venue UAT, and the
  remaining manual accessibility review.
- Push, PR, merge, production configuration, non-test data migration, and any paid-provider call.

## Rollback and next safe gate

The unperformed gates above describe the CRA-119 acceptance boundary on 2026-09-02, not current
provider inventory. CRA-121 subsequently provisioned isolated Railway staging and is accepted and
Done. CRA-122 Stage 1 is complete; Stage 2 planning is active. Application deployment and Resend
acceptance remain unperformed in the latest recorded evidence. Exact targets and rollback gates
are in the [Stage 2 plan](../deployment/staging-cra-122.md).

The 2026-09-04 audit identified missing explicit Caddy HTML/asset cache policy and the broader
`/api/*` proxy matcher relative to the CRA-119 draft contract. Existing static tests do not cover
those requirements. These are corrective-work inputs, not new passing evidence. Accepted published
history must not be rewritten; any application correction needs a separately accepted artifact SHA.
