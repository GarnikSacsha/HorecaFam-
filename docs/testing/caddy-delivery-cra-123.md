# CRA-123 local Caddy delivery evidence

Date: 2026-09-04. State: locally verified candidate; Denys subsequently authorized the three
mapped local commits. Publication and deployment remain unauthorized. Canonical issue:
[CRA-123](https://linear.app/craftspacee/issue/CRA-123/correct-caddy-staging-cache-health-and-api-routing-contract).

## Changes and boundary

The frontend Dockerfile now creates the system account it selects with `USER caddy`.
Caddy serves `/healthz` as `ok`, keeps HTML and SPA deep links `no-store`, proxies only `/api/v1`
and its descendants with method/path/query preserved, and rejects other `/api` routes.
Hashed existing assets receive immutable caching only on successful or 304 responses. Missing
assets return 404; asset errors cannot inherit the immutable policy. Existing security headers
remain. Backend API, schema, authentication, dependencies and UI source are unchanged.

`frontend/caddy-http.test.mjs` tests the actual image and its built assets. It verifies the
image's Caddyfile against the working file to reject a stale configuration. The fixture uses a
unique Docker bridge network, a synthetic Node upstream and a web port bound only to 127.0.0.1.
It removes only its own containers/network. No staging service, credentials, email or database
is used. Docker Desktop was already installed and was started for these checks.

## RED and GREEN

Run from `frontend/` with the existing Node/pnpm and a Linux Docker engine:

```powershell
rtk docker build --tag horeca-cra123-web-test .
rtk docker pull node:24-alpine
rtk proxy node --test caddy-http.test.mjs
rtk proxy node --test deployment-artifacts.test.mjs ../.railway/topology.test.mjs
rtk pnpm test
rtk pnpm typecheck
rtk pnpm lint
rtk pnpm format:check
```

- Original Dockerfile: build failed at `chown`, because `caddy:caddy` did not exist. Frontend
  compilation itself succeeded. Creating the account made the image build pass.
- Original Caddyfile in that runnable image: **3 passed, 5 failed, 0 skipped**. Failures proved
  missing health content, missing HTML and asset cache headers, SPA returned for missing assets,
  and unsupported API routes accepted. This is the behavior RED.
- First correction: **8 passed, 0 failed, 0 skipped**.
- Fresh review added a case for errors on existing assets: **8 passed, 1 failed, 0 skipped**.
  An error response incorrectly carried immutable caching. Restricting the header by response
  status fixed it. Final HTTP gate: **9 passed, 0 failed, 0 skipped**.
- Actual Caddy validation and non-root startup are included in the HTTP gate. Caddy emits a
  non-failing formatting warning for the repository's existing space-indentation style.
- Static frontend/topology tests: **5 passed, 0 failed, 0 skipped**.
- Vitest: **72 passed across 21 files, 0 failed, 0 skipped**. TypeScript passed. Production
  compilation ran successfully inside the final Docker build (67 modules).

One initial HTTP invocation failed during fixture setup because an internal Docker network did
not expose the requested host port. It is not behavior RED; the fixture uses a dedicated bridge
network with loopback-only publishing. Sandbox-limited Prettier attempts could not resolve the
installed executable; rerunning against the existing dependencies outside the sandbox succeeded.
ESLint identified missing explicit Node-global references in the new test; these were corrected.
Final ESLint and Prettier checks passed with exit 0.

After local-commit authorization, the combined HTTP/static pre-commit command initially failed
because the local test image was absent (5 passed, 9 fixture failures). Rebuilding the image and
preparing the same Node base restored the fixture: **14 passed, 0 failed, 0 skipped**.
The rebuild retained runtime config digest `be13c3bdf69a8ecdbbefc1616cdd810098f324eafebdf69b8454f93869330910`;
its new manifest list is `sha256:481accc6c86f2f59ff1c15d64c80b7183ec48f6908043d108a917c14da4e507b`.

## Artifact evidence

Local web image build manifest list:
`sha256:9ba01aca2ace5f92b3b407516acfd2dab28c3a5a4697b846c45ebea3366fdbe1`.
Runtime image config:
`sha256:be13c3bdf69a8ecdbbefc1616cdd810098f324eafebdf69b8454f93869330910`.
Base images used:

- Caddy: `sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d`.
- Node: `sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf`.

These are local test artifacts, not published application SHAs. No accepted candidate SHA exists
for the uncommitted correction. Base tags remain mutable; record digests again when publishing.
Final test-only Node import changes do not alter the tested Caddyfile or Dockerfile.

Related CRA-122 preflight also built the unchanged backend Dockerfile successfully as
`horeca-cra122-backend-test`, manifest list
`sha256:ecc3ec94c7dd1f38c3f94d5529e3c998e099b07caa54a270e219c0f73b407720`.
A disposable `--network none` container successfully imported `app.api_server`, `app.worker`
and `app.cron` and asserted a nonzero UID. This is import/user smoke only, not application startup,
migration, database integration or worker delivery acceptance.

## Review and next step

The final fresh self-review checked route ordering, preserved proxy paths, fallback isolation,
asset error caching, non-root startup and fixture cleanup. No independent reviewer was used.
Full PostgreSQL regression and Playwright were not rerun for this configuration-only correction;
their earlier accepted counts remain historical. Real staging health/auth/email/storage/cron,
backup/restore, load testing and venue UAT remain unproven.

Intended single corrective commit: `fix(web): enforce Caddy delivery boundaries`.
Selective paths: `frontend/Caddyfile`, `frontend/Dockerfile`,
`frontend/deployment-artifacts.test.mjs`, `frontend/caddy-http.test.mjs`, and this evidence file.
At verification time no staging, commit, push or deployment had occurred. The subsequent user
authorization permits this selective local checkpoint only. Preserve unrelated `Photos/`, `outputs/` and
the pre-existing metadata-only `question_generation.py` status.

After acceptance and separately authorized publication, record the replacement application SHA
in CRA-122 before source binding. Follow the
[canonical Stage 2 plan](https://linear.app/craftspacee/document/cra-122-stage-2-staging-source-variables-and-rollback-plan-dde7a78ff215).

Reference: Caddy's [ordered routes](https://caddyserver.com/docs/caddyfile/directives/route) and
[response-matched headers](https://caddyserver.com/docs/caddyfile/directives/header).
