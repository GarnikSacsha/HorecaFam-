# CRA-122 Stage 2 — staging execution plan

**Prepared:** 2026-09-04. **State:** review draft; no provider execution authorized by this file.
**Canonical task:** [CRA-122](https://linear.app/craftspacee/issue/CRA-122/deploy-and-accept-staging).
**Release gates:** [CRA-78](https://linear.app/craftspacee/issue/CRA-78/plan-pilot-release-readiness-and-first-venue-uat).

## Scope and evidence boundary

Denys requested status synchronization, this plan and bounded correction preparation after the
2026-09-04 audit. CRA-121 is accepted and Done. CRA-122 Stage 1 is complete; the provider inventory
below was observed on 2026-09-03, not freshly inspected today. Do not interpret a resource ID or
local green check as current provider health. No source binding, secret entry, migration, deploy,
email send, synthetic staging data, production action or local commit has occurred in this work.

Application baseline: `2644b796b122b9d160392f8e95cc515e736f7de9` from
`GarnikSacsha/HorecaFam-`, branch `main`; GitHub remote was verified during the audit.
Local `78952feb1613ce367ecb5b272ca70ba0da1fc1fa` is documentation-only. Never upload the dirty
working directory. Exclude `Photos/`, `outputs/`, every `.env*`, credential, cache and local helper.

Authorized local CRA-123 corrective checkpoint: `ec27d19e023dc48f7a66103967c5d23f23281bfe`.
It is not published or bound to staging. Deployment-candidate acceptance and publication remain
separate gates; the published baseline above has not changed.

CRA-123 is locally corrected and verified, pending Denys acceptance and publication; see
[the exact evidence](../testing/caddy-delivery-cra-123.md). The Caddy findings require an accepted
corrective disposition before rollout. If application files
change, the old baseline is no longer the deployment candidate: record a separately accepted,
committed and published replacement SHA here and in CRA-122 before provider execution. Do not
silently deploy a branch's newer tip or mix application SHAs across services.

## Existing staging targets

Workspace: `garniksacsha's Projects`, last observed Hobby plan; infrastructure owner: Denys.
Project: `04320f63-ab40-426f-ab35-02fcb365c3b8` (HoReCa Training Platform).
Environment: `d8e64109-9863-4faa-a45e-f072adb3cfac` (`staging`), EU West / Amsterdam.

| Resource | Existing ID | Boundary |
| --- | --- | --- |
| postgres | `54c1a13f-c342-4490-aa32-0b6f7407f94f` | PostgreSQL 16, private; no source change |
| postgres volume | `95241152-3289-4117-94ac-73fdf58f8800` | Preserve; no deletion or replacement |
| learning-assets | `3534c2c4-a42c-4954-82a4-9a3a024fc55e` | Private staging bucket; last observed empty |
| api | `785ae5f7-9052-4a1b-92ea-e8524236de97` | Private, port 8000 |
| worker | `5028af74-ea48-4c31-97d7-042ae0c5836d` | Private, no HTTP healthcheck |
| migration-runner | `c7d4489f-75c1-4a4a-8f85-39e8cd2737b1` | One controlled run, no schedule/restart loop |
| web | `167269a6-26cb-40f6-b129-b698127c87ee` | Only public service, port 8080 |
| cron-stale-jobs | `f6ab8054-ffba-4e8e-a217-206d9e396b06` | Private terminating command |
| cron-attempt-expiry | `4d78a477-8439-473a-899f-7a7ad055814e` | Private terminating command |
| cron-retake-deadlines | `c8f63848-2e5c-4fbf-a5d5-c8c5f0404c43` | Private terminating command |
| cron-security-cleanup | `9c3a978f-325a-4e9d-a5c1-700ba0f4575c` | Private terminating command |
| cron-audit-retention | `b2e10228-f0d5-4328-89d5-6ebd3eb055e8` | Private terminating command |

Public browser origin: `https://web-staging-4268.up.railway.app` over standard HTTPS.
Port 8080 is the container target, not a port to append to the public URL.
PostgreSQL's last successful deployment ID was `46bb859f-58c8-4318-aa5a-1aacbf62d522`.

## Source, build and startup matrix

Use the existing Dockerfiles; no Railpack replacement, dependency addition or new IaC apply.
All eight backend application roles use the same accepted source SHA and backend build context.
Railway must use `Dockerfile` relative to each service root. Leave build-command overrides empty.

| Service | Root | Start command | Health / schedule |
| --- | --- | --- | --- |
| api | `/backend` | `python -m app.api_server` | `/api/v1/health`, port 8000 |
| worker | `/backend` | `python -m app.worker` | Lease/heartbeat/log checks; no HTTP probe |
| migration-runner | `/backend` | `python -m alembic upgrade head` | Exit 0 once; head `0018_job_runtime` |
| cron-stale-jobs | `/backend` | `python -m app.cron stale-jobs` | `*/5 * * * *` UTC |
| cron-attempt-expiry | `/backend` | `python -m app.cron attempt-expiry` | `0 * * * *` UTC |
| cron-retake-deadlines | `/backend` | `python -m app.cron retake-deadlines` | `10 * * * *` UTC |
| cron-security-cleanup | `/backend` | `python -m app.cron security-cleanup` | `15 1 * * *` UTC |
| cron-audit-retention | `/backend` | `python -m app.cron audit-retention` | `15 2 * * *` UTC |
| web | `/frontend` | Docker CMD: `caddy run --config /etc/caddy/Caddyfile --adapter caddyfile` | Port 8080; `/healthz` in CRA-123 candidate, pending acceptance |

The API entry point uses Uvicorn factory `app.main:create_app`, not `app.api_server:app`.
API health is deliberately liveness-only; HTTP 200 does not prove database or auth readiness.
Cron must exit and close connections; it must not inherit the API command or HTTP healthcheck.

Proposed runtime policy: one instance per role for this staging gate; API/worker/web always-on,
bounded on-failure restart, migration/cron no automatic retry loop. Exact resource limits,
restart settings and budget ceiling require provider review and Denys acceptance before binding.
Record actual image/deployment identifiers: current Docker base tags and Python version ranges
are not a promise of bit-for-bit reproducible builds from SHA alone.

## Source binding without premature rollout

1. Recheck remote SHA and all target IDs, region, ownership, exposure and pending provider changes.
2. Inspect the source-binding mechanism without applying it. Resolve how initial deployment is
   prevented; disabling later push triggers alone does not prove initial binding cannot deploy.
3. After explicit source/setting approval, stage only the reviewed source/root/start settings.
   Keep automatic deployments disabled. Do not click Deploy Latest Commit during configuration.
4. Preserve cron non-execution until migration completes. If binding immediately makes existing
   schedules runnable, stop and obtain approval for the exact schedule-suspension/restoration map.
5. Before any run, prove every application role resolves to the accepted SHA. Branch `main`
   alone is insufficient. If the UI cannot hold the SHA or suppress initial execution, stop and
   review an alternative immutable-artifact mechanism; do not invent one at execution time.

Do not apply `.railway/railway.ts`: it sets `APP_ENV=production` and models only four resources.
The existing staging inventory is authoritative for this plan; no recreation or rename is needed.

## Environment and secret reference matrix

All settings belong only to the resolved staging environment. Denys owns approval and revocation.
Do not introduce inherited production variables. Below are variable names and intended sources,
never credential values. Secret entry remains a separately approved provider-side operation.

| Names | Consumers | Source / handling |
| --- | --- | --- |
| `APP_ENV`, `LOG_LEVEL` | API, worker, cron | Explicit staging / INFO configuration |
| `APP_ENV`, `DATABASE_URL` | migration-runner | Staging and dedicated migration identity |
| `DATABASE_URL` | API, worker, cron | Private staging PostgreSQL, minimum required runtime permissions |
| `MFA_ENCRYPTION_KEYS`, `AUTH_THROTTLE_HMAC_KEY` | API | Staging-only cryptographic keys |
| `INVITATION_TOKEN_HMAC_KEYS`, `PASSWORD_RESET_TOKEN_HMAC_KEYS` | API, worker | Same ordered staging key sets for issuance and delivery |
| `CORS_ALLOWED_ORIGINS` | API | JSON list containing only the public staging HTTPS origin |
| `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE` | API | `true`, `lax`; preserve host-only cookies |
| `STORAGE_BUCKET`, `STORAGE_ENDPOINT_URL`, `STORAGE_REGION` | API | Exact existing staging bucket metadata |
| `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY` | API | Independently revocable staging bucket credentials |
| `PUBLIC_APP_URL` | worker | Public staging HTTPS origin, without internal port |
| `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` | worker | Approved staging sender/key, no unrelated domain reuse |
| `WORKER_ID`, `WORKER_IDLE_SECONDS`, `WORKER_HEARTBEAT_INTERVAL_SECONDS` | worker | Unique runtime identity, proposed timings 1s / 15s |
| `PORT` | API / web | 8000 / 8080 respectively |
| `API_UPSTREAM` | web | Private API DNS on port 8000, verified inside staging |

Key arrays use the JSON-list encoding expected by Pydantic. Secrets must not be validated by
printing Settings, environment dumps or provider variable values.

The migration environment bypasses `Settings.require_async_postgresql`; its `DATABASE_URL` must
already use `postgresql+asyncpg`. Resolve a provider-side secret reference/composition for that
URL before migration. Do not copy a raw PostgreSQL URL into chat to transform it.

Separate migration and runtime DB identities are required by the security contract. CRA-121 does
not prove their grants exist. Determine role/grant setup and its exact SQL under a separately
approved non-test database action; do not simply give every service the database administrator.

Worker startup calls `validate_worker_readiness()`: Resend key, sender, public URL and signing
keys are prerequisites for Stage 5. Stage 8 tests delivery later; it cannot postpone configuration
until after worker startup. Synthetic email-producing actions must wait for recipient/send approval.
There is no staging fake-provider switch in the accepted production composition.

Rotation/revocation: version HMAC/MFA key sets deliberately and coordinate API/worker changes;
do not remove an old signing key while valid issued links depend on it. Rotate DB and storage
credentials by their own identities, and revoke the Resend key independently. Exact operator steps
and retention overlap are reviewed before secret creation. No Sentry DSN or SDK is included.

## Ordered execution and evidence

1. **Stage 2 acceptance:** resolve the blocker table below and accept the exact source/settings map.
2. **Stage 3:** bind only approved sources/settings and secret references, preventing execution.
   Record names, IDs and SHA only. No secret value may enter logs, screenshots or Linear.
3. **Stage 4:** separately approve one migration-runner invocation. Verify private DB target,
   pre-migration state and recovery decision; run once, capture exit status/head. No auto-upgrade
   on API startup and no retry after an ambiguous result without reconciliation.
4. **Stage 5:** separately approve API, worker and then five cron rollouts; require migration
   success first. Verify liveness, actual DB/auth path, lease/heartbeat/lost-lease denial and exit.
5. **Stage 6:** deploy web last. Check health, deep-link SPA fallback, cache/security headers,
   `/api/v1/health`, cookies, CORS, CSRF and private API exposure from the actual origin.
6. **Stage 7:** after synthetic-data approval, run the complete CRA-78 section 6 matrix including
   invitation, Pending, activation, learning, Practice, Final, Result, Attention, recovery and
   lifecycle/history. Run each cron twice for the same logical bucket and prove no duplicate effect.
7. **Stage 8:** after sender/key/recipient/send approval, prove invitation/reset delivery and
   controlled idempotent retry. Correlate provider IDs with Job/attempt state without message bodies.
8. **Stage 9:** record UTC times, application SHA, image/deployment IDs, counts, logs redaction,
   migration result, rollback targets and limitations. Denys accepts; zero required skips.

## Rollback boundary

There is no previous accepted application deployment in staging. Before migration, failure means
stop without rollout and preserve the existing database/bucket. After migration, leave the schema
and data intact for diagnosis; never run automatic downgrade, truncate, delete or recreate.

Failed application rollout: do not deploy later roles or serve public traffic; capture redacted
evidence. Stop/redeploy actions need the applicable approval and exact deployment IDs. A future
artifact rollback requires proven schema compatibility. Database recovery requires a separately
approved isolated restore target and cutover plan; it is not part of a blind retry.

Protected rollback targets are the exact service/volume/bucket IDs above. No deletion, source
history rewrite or production mutation is part of this plan. Load testing, backup/PITR/asset
recovery, Bacara data, physical UAT and production release remain subsequent CRA-78 gates.

## Open blockers before provider mutation

| Blocker | Required closure |
| --- | --- |
| Caddy cache/proxy/health contract | CRA-123 local GREEN: 9 HTTP checks; Denys acceptance and publication remain |
| Application SHA after correction | Explicit acceptance, selective commit/publication, all-role SHA map; never deploy uncommitted changes |
| Initial source binding / immutable selection | Read-only provider inspection and a mechanism proving no premature build/run |
| Existing cron schedules | Reviewed way to prevent execution before migration, with restore order |
| DB runtime/migration identities | Grants and async URL reference resolved without exposing values |
| Resend sender/key/recipients | Owner-approved staging configuration before worker; sends separately approved |
| Storage credentials and networking | Least-privilege credential scope and private access verified |
| Spending/resources | Explicit staging budget and per-service limits; Hobby label is not a spending cap |
| Docker verification | Local frontend/backend builds passed; Caddy HTTP and backend import/non-root smoke passed. Live backend/DB/provider operation remains a staging gate |

## Local commit boundaries

Denys explicitly authorized these three selective local commits after reviewing the completion
report. This authorization does not cover push, provider settings, migration or deployment.

1. `fix(web): enforce Caddy delivery boundaries` — CRA-123's separate bounded map, including
   the exact evidence file. This precedes documentation that links to the evidence.
2. `docs(deploy): define CRA-122 staging execution plan` — this file and its canonical Linear
   planning counterpart. Verify commands against code, resource IDs against CRA-122, variable-name
   inventory, approval boundaries and open blockers. Documentation-only TDD exception applies.
3. `docs(project): synchronize CRA-122 deployment checkpoint` — README, STATUS, CONTEXT,
   backend README, architecture/testing indexes, `.harness/GIT-WORKFLOW.md`, `.harness/TESTING.md`,
   and corrected historical CRA-119 evidence wording. Verify exact diff, links, stale statuses and
   absence of secrets/local runtime data.

No Git index change or local commit is implied. Product/API/schema contracts are unchanged.

## Provider references reviewed on 2026-09-04

- [Railway monorepo roots](https://docs.railway.com/deployments/monorepo).
- [Railway GitHub autodeploy controls](https://docs.railway.com/deployments/github-autodeploys).
- [Railway terminating cron jobs](https://docs.railway.com/cron-jobs).
- [Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys).

These explain platform behavior; they do not prove the current account's settings or permissions.
