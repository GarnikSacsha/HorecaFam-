# CRA-122 live staging acceptance runbook

## Current routing — 2026-09-16

Use [STATUS](../../STATUS.md) and [the reconciliation ledger](../testing/reconciliation-2026-09-16.md) before the dated records below.
September 15 CRA-233 delivery and September 16 authenticated UI evidence supersede the older
worker-offline, mail-unsent and Employee-not-activated descriptions: one Employee is active;
Menu and Training remain empty unpublished drafts with no assignments. CRA-234 is local-only.
Accounts, activation, CORS application and completed migrations must not be repeated.

The older source/build JSON files are historical preparation inputs, not the current delivery
manifest: source binding was not applied, the build settings were applied in their recorded
September 7 boundary, and scoped CORS was applied in its September 13 boundary. Do not reapply
or retarget these files from this documentation. The current live source is the sealed CRA-233
packet; publication, further deployment and non-test content writes remain separate decisions.

Dated observations, test counts and original runbook requirements below retain their original
scope. They do not establish fresh provider state or override this current routing.

## Authorized worker and CORS execution — 2026-09-13

See the [execution checkpoint](staging-preflight-2026-09-12.md) before older instructions.
The prepared worker deployment reached SUCCESS and is Online; scoped bucket CORS is applied.
Allowed-origin OPTIONS and disallowed-origin rejection both passed. No actual upload yet.
The existing key has Sending access, but Resend rejected the existing invitation with 403
because resend.dev permits only the account-owner test recipient. No accepted send observed;
existing retries were not modified. There is no verified sender domain. Resolve the sender
domain or explicitly authorized test recipient before claiming mail/Employee acceptance.
Do not repeat bootstrap, grants, CORS application or deployment to fix this provider restriction.
This checkpoint changes documentation only; no application edits, commit or push.

## Fresh preflight — 2026-09-12

Read [the current preflight and exact next-operation packet](staging-preflight-2026-09-12.md)
before using older account instructions. Operator/Organization/Admin setup already exists;
one invitation email is pending while worker is offline. Do not repeat bootstrap or provisioning.
The bucket is reachable but browser CORS is not configured; a scoped proposal is prepared.
Local focused backend, frontend and three-viewport browser gates pass; live Employee acceptance,
content publication and mail/storage writes remain unperformed. No provider mutation or commit.

## Web rollout complete — 2026-09-11

Denys explicitly authorized upload/deployment of only the existing staging web service from
commit `0956e7bb1af8914b94bc064e65e6cfaf4f88a775`. Its 377-file isolated source export was
rechecked immediately before upload: zero hash mismatches or additional files. No Git push.

Deployment `e9a14512-7a57-474b-9bb1-26402cc933f7` is SUCCESS and not stopped.
Dockerfile/frontend build execution was observed; final status and HTTPS checks confirm delivery.
Public origin: https://web-staging-4268.up.railway.app.

Fresh HTTP smoke: **9 passed, 0 failed, 0 skipped**. `/healthz`, `/`, `/login` and
`/api/v1/health` return 200; `/api`, `/api/v2` and a missing asset return 404.
Health/HTML use no-store and the expected nosniff/referrer headers. Existing hashed JS/CSS return
200 with immutable caching; missing assets do not. Browser inspection confirmed the rendered
Bacara public entry and its navigation to the login form. This is not authenticated acceptance.

No API/worker/cron redeploy, migration, account setup, provider send, configuration change,
dependency change, local commit or push occurred. Worker/provider/storage readiness, guarded
accounts, content publication and full Admin/Employee journeys remain open. CRA-122 stays
In Progress. Next bounded step is worker/provider/storage preflight; account execution remains
separately approved and secrets stay in the owner's private input channel.

## Executable account preparation — CRA-171 — 2026-09-11

The [one-time provisioning operation](../testing/account-provisioning.md) now implements the
initial operator and separate Organization Admin setup. Its 29 focused tests pass, including
actual Admin login requiring normal MFA enrollment. This supersedes the specification-only
wording below. Staging execution is still unperformed and needs a reviewed artifact plus
separate migration/account-apply approval. An in-app owner provisioning cabinet is deferred.


## Current staging state — after API rollout, 2026-09-11

Follow the [verified staging checkpoint](../../STATUS.md#verified-staging-checkpoint--2026-09-11-after-api-rollout).
CRA-171 is committed at `0956e7b`; migration and runtime grants completed in the preceding task,
and API/web are running. Worker, account setup and authenticated acceptance remain open.
The earlier snapshot below is historical and must not drive repeated migration or setup actions.

## Earlier current delivery checkpoint — 2026-09-11, before migration/API rollout

Denys authorized synchronization and continuation of the audited delivery plan. CRA-131 public-start visual review is explicitly accepted; copy refinement and additional animation are deferred. This accepts the existing local visual iteration, not a new asset or deployment operation.

The six CRA-131/147/149/150/151/170 implementation maps are already committed as 16 local checkpoints ending at ede4281. GitHub main remains fafec73ad7f3438e1b545acea7cde3018b7f2fbf (direct read on September 11); local main is ahead 16, behind 0. Do not recommit these implementations. Selected staging source remains fafec73 until an explicit replacement selection.

September 10 recorded full verification: 865 backend, 89 Vitest and 69 Playwright passed; final successful runs have zero failures/errors/skips. Independent coverage: 93.96% statements, 80.46% branches, 89.77% fixed critical aggregate. These are recorded results, not September 11 reruns. Exact 16-checkpoint ledger: docs/testing/demo-candidate-2026-09-10.md. CRA-123–126 remain accepted and Done; remaining feature acceptance is distinct from local commit completion.

September 11 read-only Railway inventory: PostgreSQL has one active SUCCESS deployment; all nine application services have no repository/image source and no latest or active deployment. Five cron schedules remain null. Pending-setting count is unavailable in this response; prior secret/reference/login evidence is not a fresh connectivity or permission check.

Accepted account direction: Denys arranges Alexandra's initial Organization Admin access; Alexandra then invites employees by email using the existing Organization-scoped flow. Denys selected a protected one-time Admin setup now, with an in-app owner provisioning cabinet deferred. Keep the technical Platform Operator separate; do not grant Alexandra platform access. Do not add operational roles implicitly. CRA-171 owns the bounded initial operator and separate Admin implementation; non-test apply remains separate.

Today's order: synchronize evidence; implement/test one-time account provisioning; review the exact immutable delivery candidate/settings and migration/recovery boundary; perform separately authorized rollout; only then real-origin Admin/Employee acceptance. No new commit, push, deployment, email or non-test data operation is performed by this synchronization.

Older uncommitted/no-full-regression and visual-review-pending statements below are superseded by this checkpoint.

## Current preparation — 2026-09-09

This section supersedes obsolete next-action wording below. CRA-123–126 are accepted and Done.
Selected source remains `fafec73` / schema `0019_auth_security_budgets`; local CRA-131/147/149/150/151
changes require their own reviewed publication and a replacement candidate before rollout.
Denys requires Dashboard and logout of other devices before the demo. Their local implementations
are tracked by CRA-151 and CRA-150, pending owner acceptance and publication; they are not deferred.

Latest **recorded September 8** provider preparation is 44 pending changes: migration 2, API 16,
worker 9, five cron services 3 each, web 2. Application keys and storage/signing references are
present. Both DB-role private TCP login checks passed using owner-entered passwords. Do not
recreate roles, re-enter keys or repeat LOGIN changes. These checks do not prove resolved service
DATABASE_URL connectivity, storage operations or post-migration grants. No fresh provider inventory
or mutation is claimed here. September 9 public `/healthz` returned HTTP 404 with Railway fallback.

### First-login operation specification — prepared, not executed

The first identity operation must run only after the authorized migration and grant checks,
from the deployed reviewed backend artifact in the exact staging database. Its inputs are the
approved technical operator email and a password entered through an interactive hidden prompt
in the owner's provider console. Never use command-line password arguments, persistent secret
files, SQL literals, model-visible input/output or provider log output for the password/hash.

The concrete transaction specification is:

1. Verify `APP_ENV=staging`, expected database identity and revision 0019; stop on mismatch.
   Use the existing Settings/session factory and `normalize_email`.
2. Serialize the bootstrap transaction with an advisory lock. Query the exact normalized User
   and platform AdminAccess scope. If an identical active operator already exists, report only
   `existing`; do not reset their password or change privileges. Any partial/colliding state stops.
3. Hash the supplied password with existing `PasswordManager.hash_async`; no custom hashing.
   Insert one User (`email_normalized`, `password_hash`, `preferred_locale=uk`) and one AdminAccess
   (`scope=platform_operator`, `organization_id=NULL`, `status=active`). Do not manufacture
   email-verification evidence, sessions, MFA credentials or recovery codes.
4. Append a system AuditEvent with action `initial_operator_created`, target User ID, request ID
   and outcome only; no email/password/hash payload. Commit all three rows atomically. Return only
   status and non-secret IDs; rollback on any error. Replay must preserve IDs and create no rows.
5. Execute the existing `bootstrap_venue` dry-run/apply/replay sequence below, using the reviewed
   spec. Complete real password login and normal MFA enrollment; test both granted scopes.

This specification is not yet an executable or test-verified helper. Creating that helper needs
its own bounded implementation issue; CRA-122 forbids production-code changes. Its non-test apply
also needs separate approval. The existing venue CLI cannot create the first User.

The technical operator is separate from Alexandra's demo Admin and Employee identities.
`bootstrap_venue` grants organization-admin access to that operator only. Provisioning the separate
demo Admin therefore needs an explicit organization-scoped grant operation after the User exists;
the Employee invitation flow cannot grant Admin. Do not give the demo Admin platform scope or
silently substitute the operator for that persona. Validate real MFA and UI routing for each account.

### Publication and resource preparation

Preserve the existing maps in [public entry](../testing/public-start-editorial.md),
[Employee profile](../testing/employee-profile.md), [Practice](../testing/practice-reference-families.md),
[other-device logout](../testing/logout-other-devices.md) and [Dashboard](../testing/admin-dashboard.md).
Review CRA-131 before CRA-147 or stage their separate `App.tsx` hunks. No whole-worktree staging;
exclude `Photos/`, `outputs/`, secrets and runtime artifacts. Final September 9 shared verification:
89 Vitest passed; Playwright completed successfully with 69 configured cases and no failed tests.
Format/lint/production build passed; browser APIs are mocked. Exact evidence is in the testing index.
Public photo overlays and fallback font remain visual acceptance limitations.

Current recorded 8 vCPU/8 GB per-service limits are ceilings, not consumption estimates. Proposed
first measurement boundary: one replica per role, five cron schedules still null; measure idle
API/worker memory and two concurrent password hashes before selecting lower RAM caps. Do not
claim the agreed $20/month budget is enforced without fresh provider controls/usage evidence.
Apply no resource reduction until the concrete cap and observed headroom are reviewed.

After local feature acceptance/publication: refresh all nine provider targets, resolve delivery,
review exact candidate/settings, migrate once, verify grants, roll out in the ordered gates below,
then run real-origin synthetic acceptance. Actual Bacara import and the two-person UAT remain
separate from synthetic staging checks. No provider action is authorized by this preparation.

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

## Current preparation ownership — 2026-09-08

Latest readback: Denys saved API runtime DATABASE_URL; worker and all five cron services now
have staged DATABASE_URL references to API. There are 34 pending changes. The DB entry and
six-reference wiring step is complete as configuration preparation, not proof of credentials
or successful database connectivity. Application keys and scoped storage configuration are
the next remaining inputs; the earlier 27-change/DB-entry wording below is historical.

The [configuration checkpoint](staging-cra-122.md#configuration-preparation-checkpoint--2026-09-08)
records 27 pending Railway changes: owner-entered migration DATABASE_URL and 26 non-secret
settings across nine services. None were applied or deployed in this continuation.
Both DB roles already have LOGIN; passwords were entered privately. Do not repeat those steps.
The support question was sent and checked; no supported source-binding solution is available yet.

Next owner participation is private entry of the API runtime-role DATABASE_URL, followed by
the missing application key sets and scoped storage credentials. The agent can subsequently
wire runtime DB references to worker/five cron services and shared signing-key references to
worker without exposing their values. Connection success remains unproven. Resource caps,
delivery, first operator and separate migration/rollout acceptance gates remain open.
The earlier ownership table is historical wherever it asks to resend support or set DB LOGIN.

## Next-step ownership — 2026-09-08

This continuation prepares prerequisites under CRA-122; accepted candidate remains fafec73.
One documentation boundary: this section only. Verify its links and diff; no code tests apply.

| Item | Agent preparation | Denys action and timing |
| --- | --- | --- |
| Delivery guarantee | Prepared the exact [Railway support question](cra-122-source-build-preparation.md); review the supported answer before preparing a source mutation | Authorize sending this technical question; no credentials or project identifiers are needed in the message |
| DB credentials | Prepare existing-role LOGIN delta and exact service mapping: migrator only to migration-runner, runtime to API/worker/five cron roles; web gets neither | Enter separate passwords through the reviewed masked provider/psql channel when the operation is ready; do not send them in chat |
| Storage and email | Verify API-only bucket references, GetObject/PutObject requirements, worker-only email credential and existing sender/recipient scope | Enter or narrow credentials in provider UI if current scope requires it; no new recipient decision requested now |
| First operator | Prepare a guarded one-time User plus active platform AdminAccess transaction using the existing password service; stop on collisions; no bootstrap before this identity exists | Enter initial password securely and complete MFA in the application after authorized deployment |
| Resources | Prepare measured limits against the already agreed $20/month budget and current placement/replica inventory | Review the concrete limits; no budget reconfirmation requested now |
| Product scope | Compare Dashboard/logout-all requirements with implementation and prepare explicit disposition options | Decide those options when presented; no silent deferral |
| Execution | Prepare exact migration, rollout and synthetic acceptance operations with target IDs and recovery steps | Approve the concrete external operations once ready |

Fresh static checks confirmed the initial-operator dependency and existing password-service reuse.
Official [Railway cron documentation](https://docs.railway.com/cron-jobs) describes scheduled start
commands and skipped overlapping runs. It does not establish that an initial archive upload
cannot run a service with a null schedule. The archive alternative therefore still needs its
initial-execution boundary reviewed, especially for migration and cron roles.
No live Railway inventory refresh, credentials, message send, code change or deployment occurred.

## Decision packet — 2026-09-08

This packet implements Denys's request to prepare the next step under CRA-122.
It is a proposal, not formal issue acceptance or authorization to change staging.
It takes precedence over the older execution examples below **only after candidate selection**;
until then those examples must not be executed against newer main.

### 1. Code acceptance proposed to Denys

| Issue | Published boundary | Verified evidence already recorded | Acceptance limit |
| --- | --- | --- | --- |
| CRA-123 | `ec27d19` | 9 actual Caddy HTTP checks passed | Container/browser delivery correction; no fresh Docker rerun or live staging result |
| CRA-124 | `e18af71` | 34 focused tests passed | S3 addressing correction; live bucket/browser upload remains pending |
| CRA-125 | 10 commits `d24e7a2..2275cee` | Full PostgreSQL run: 809 passed, 0 failed/skipped; statements 94.01%, branches 80.42%, critical aggregate 89.60% | Coverage closure and three verified corrections; no staging acceptance |
| CRA-126 | `6e2665e`, `0083ddf`, `034bb5c`, `fafec73` | Full PostgreSQL run: 832 passed, 0 failed/errors/skipped; statements 93.86%, branches 80.19%, critical aggregate 89.67%; Ruff, mypy and test-DB migration checks passed | Assessment isolation, auth budgets/password concurrency, protected asset finalization; live resource/storage/migration checks remain pending |

Recommendation: accept these four published implementation outcomes with their recorded limits.
Keep CRA-122 open for real staging acceptance. Do not sum overlapping focused and full test runs.
No tests in this table were rerun while preparing this packet. Evidence:
[Caddy](../testing/caddy-delivery-cra-123.md),
[coverage closure](../testing/coverage-closure-plan.md),
[security fixes](../testing/security-fixes-cra-126.md).

### 2. Candidate decision proposed to Denys

Select `fafec73ad7f3438e1b545acea7cde3018b7f2fbf` for all nine application roles,
with Alembic head `0019_auth_security_budgets`.
The previously accepted candidate remains `2275cee1ae46da708f33a032229e708c73a966c8`
until that selection is explicit.

After selection, the source draft needs exactly nine candidate-SHA replacements, reviewed
against the existing service IDs. Do not reapply the already committed build/settings package.
The two JSON drafts have not been changed by this packet. Selection does not authorize
source connection, upload, credentials, migration, synthetic writes or deployment.

### 3. Ordered staging gates

| Gate | Concrete operation and exit evidence | Current disposition |
| --- | --- | --- |
| A — select | Record acceptance disposition and one immutable candidate for all nine roles | Awaiting Denys |
| B — refresh inventory | Read current project/environment, source, deployment/trigger counts, five schedules, DB revision, bucket occupancy and resource limits without printing secrets | Last recorded state only; repeat before any mutation |
| C — delivery | Demonstrate supported source binding with no immediate deployment and no future push trigger, or approve the explicit archive-delivery alternative in the source preparation document | Binding guarantee unresolved |
| D — prerequisites | Review exact secret destinations, existing-role LOGIN and grants, API storage GetObject/PutObject, worker sender scope, memory/replica/cost controls and initial operator setup | Separate concrete operations still needed; no role recreation |
| E — migrate once | Run the pinned migration role alone; verify revision 0019, the expanded action constraint and runtime grants | Requires explicit non-test migration authorization |
| F — runtime | Start API, verify private health and DB/storage connectivity; then worker; then web and real-origin cookie/CSRF/MFA checks | Requires rollout authorization; five schedules stay null |
| G — cron | Exercise each of five approved commands twice with controlled synthetic data and idempotency evidence, then separately enable reviewed schedules | Requires synthetic writes/cron authorization |
| H — accept | Complete this runbook's real-origin ledger, security additions below, email cases in the exact approved recipient scope, redacted logs and open-contract dispositions | Not run; Denys release decision remains outstanding |

All nine roles are API, worker, migration, web, stale-jobs, attempt-expiry,
retake-deadlines, security-cleanup and audit-retention. Stop at the first failed gate.
A successful build is not proof of a healthy deployment. Capture the source SHA,
deployment ID, actual Dockerfile/build use and resulting artifact identity for every role.
Base-image tags and backend dependency ranges mean equal Git SHAs alone do not prove
bit-for-bit identical rebuilds. Preserve successful artifact identities for recovery.

For the first operator, `bootstrap_venue` needs an existing active operator and cannot create
the initial User/password/MFA identity. A reviewed one-time procedure and secret-entry channel
are required before the journey can pass. Dashboard/logout-all require an explicit canonical
disposition; neither is silently waived here. Later load testing, Bacara content/UAT and
production backup gates in CRA-78 remain outside this CRA-122 execution scope.

### 4. Migration 0019 and recovery

Static review: migration 0019 widens
`ck_auth_rate_limit_buckets_action_allowed` with `mfa` and `reauth`;
its downgrade removes those values without removing rows.
The existing test proves a test-database constraint round trip, not safe downgrade with
populated new-action rows.

Before migration, record the actual DB revision and whether non-test data exists.
At 0018, review the single-step change; at an empty DB, review the entire chain through 0019.
Any other revision or schema drift stops execution for reconciliation.
If data exists, obtain the approved recovery point and restoration procedure first.
Only the migration role executes `python -m alembic upgrade head` from the selected source.
Run `python -m alembic current`, verify the expected constraint, then apply and verify
the separately reviewed runtime grants before API startup. Never run pytest against staging.

There is no recorded previous staging application deployment to roll back to.
Default failure containment is to keep schedules disabled, stop affected writers and preserve
logs/data while choosing a reviewed forward fix. Reintroducing the old API would restore
fixed security paths and requires an explicit incident decision.
Do not automatically downgrade 0019: existing mfa/reauth rows can make the old CHECK fail.
Do not delete budget rows to force a downgrade. A populated-data downgrade or isolated restore
needs a separate reviewed procedure and authorization; test-DB evidence does not establish it.

### 5. Storage and live security additions

The API finalizes assets by reading and checking source bytes, then writing those same bytes
to a separate final object. Confirm least-scoped GetObject/PutObject permissions and private
access; the local storage fake does not establish Railway S3 compatibility or IAM correctness.

Before cutover, inventory ready objects and outstanding old upload capabilities.
If old issuers/capabilities exist, stop issuance and let the maximum 15-minute lifetime expire,
then verify integrity. Omit this waiting step only with fresh first-deployment evidence.
Do not delete orphan objects as part of acceptance; cleanup remains a separate operation.

Add these rows to the live ledger; all start **not run**:

| Case | Expected evidence after authorization |
| --- | --- |
| SEC-1 assessment isolation | Valid own-assessment path succeeds; cross-assessment access is rejected without disclosing another tenant's data |
| SEC-2 MFA/reauth budget | Controlled attempts reach the configured limit; subsequent attempts are blocked; successful and rejected requests remain correctly scoped |
| SEC-3 password capacity | Overlength password is rejected; bounded concurrent hash work fails fast at capacity; observe memory/latency without an unapproved load test |
| SEC-4 asset integrity | Valid upload finalizes and downloads correctly; invalid length/hash is rejected; overwriting the old source cannot alter finalized bytes |
| SEC-5 private delivery | Unauthorized object/API access fails; permitted signed delivery expires according to its configured lifetime |

The password-work limit is two slots per process, not a cluster-wide limit.
Resource sizing and multi-replica behavior need runtime evidence.
Record expected/actual outcomes and non-secret identifiers; never log passwords, cookies,
MFA seeds, signing credentials, presigned URLs or recipient personal data.

### 6. Work and commit boundaries

Documentation-only exception to behavior-change TDD: verify Markdown links, exact diff,
unchanged Git index and preservation of unrelated paths; no application test rerun required.

1. Acceptance packet and current-candidate execution overlay:
   `docs/deployment/staging-acceptance-cra-122.md`.
2. Supported delivery findings and navigation:
   `docs/deployment/cra-122-source-build-preparation.md`, `STATUS.md`.

These are focused additions to an already dirty documentation checkpoint, not permission to
stage entire files. A future commit must include the previously reviewed synchronization map
or selectively stage only approved hunks. No commit or push is authorized by preparation.

## Current reconciliation — 2026-09-08

Denys authorized documentation and Linear synchronization under CRA-122. Published GitHub/local
main is `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`. CRA-125's ten commits and CRA-126's four commits are published.
CRA-123/124/125/126 formal acceptance remains open.

**Version gate:** last accepted staging candidate is still
`2275cee1ae46da708f33a032229e708c73a966c8` with schema `0018_job_runtime`.
Published `fafec73` is a proposed replacement requiring explicit selection; its source head is
`0019_auth_security_budgets`. Do not deploy new main using the old migration/rollback checklist.
The JSON source draft retains the previously reviewed SHA; it has not been applied or silently
retargeted. The build JSON is retained as evidence of the reviewed input, not a request to reapply.

For a replacement candidate, review migration 0019 before API startup. Its downgrade cannot
restore the old CHECK while mfa/reauth budget rows exist; no automatic deletion is permitted.
Storage finalization needs server-side GetObject/PutObject. If old upload capabilities or ready
objects exist, stop old issuers, allow the maximum 15-minute capability lifetime to expire and
verify integrity; do not assume an empty bucket without fresh evidence. Orphan-object cleanup,
live IAM/storage smoke and non-test migrations remain separate. See the
[CRA-126 report](../testing/security-fixes-cra-126.md) for the exact rollout limitations.

**Recorded provider state, not a fresh read:** September 7 patches applied cron suspension/two
non-secret variables and the nine-service build/start package with skipDeploys=true.
Postflight: nine applications without source/deployments, zero push triggers, five null schedules.
Saved config has DOCKERFILE; ServiceInstance reports RAILPACK. Actual build use remains unproven.
The September 8 source investigation found NO_REPO autodeploy status and a side-effect-free preview;
neither proves suppression at binding time. The prepared support question remains unsent.

Next work is the supported source-binding guarantee, proposed candidate/0019 rollback review,
scoped secret/DB LOGIN/runtime grants, storage permissions, resource/cost controls, initial
operator procedure and Dashboard/logout-all disposition. Then migration, runtime/web rollout,
synthetic real-origin acceptance and provider sends use their existing separate gates.
Do not recreate roles, reregister SSH, reapply completed settings or infer release approval.
The latest recorded backend gate is 832 passed / 0 failed / 0 errors / 0 skipped, with all three
coverage gates passing. No app tests, provider queries or provider writes ran in this synchronization.
The execution details below retain dated evidence and the older accepted candidate. This version
gate takes precedence over stale current-state wording in those historical sections.

Prepared 2026-09-05; reconciled 2026-09-07. Planning only: none of the scenarios below has been executed by preparing
this document. Every evidence row starts **not run**. This is not a staging acceptance result.

Canonical scope: [CRA-122](https://linear.app/craftspacee/issue/CRA-122/deploy-and-accept-staging)
and section 6 of [CRA-78](https://linear.app/craftspacee/issue/CRA-78/plan-pilot-release-readiness-and-first-venue-uat).
Use the [source/settings/DB execution plan](staging-cra-122.md) for target IDs, approved actions,
deployment order and rollback. This document proposes the later live acceptance procedure;
it does not authorize provider settings, secrets, migration, rollout, synthetic writes or sends.

## Current authorization and readiness

Published CRA-123/124/125 corrections are included in candidate
`2275cee1ae46da708f33a032229e708c73a966c8`, explicitly accepted by Denys for all nine staging
application services on 2026-09-07. Full Stage 2 and live acceptance remain open.
The latest full local PostgreSQL 16 gate passed 809 tests, 0 failed/skipped: statements
11408/12135 (94.01%), branches 2041/2538 (80.42%), fixed critical aggregate
1293/1443 (89.60%). All three independent gates pass. See the
[coverage closure record](../testing/coverage-closure-plan.md). The earlier
[audit](../testing/repository-audit-2026-09-07.md) records 72 Vitest, 42 Playwright executions
and 5 artifact/topology checks; these were not rerun in this planning step.
These are local checks, not passing rows in this live ledger.

Both explicitly approved non-secret variables are applied in Railway settings:
API `STORAGE_ADDRESSING_STYLE=virtual` and worker `EMAIL_FROM_ADDRESS=onboarding@resend.dev`.
The approved seven-change patch also cleared all five cron schedules, with `skipDeploys: true`.
Patch `ee4d02d2-388d-46cd-a7be-49f30046b42c` is COMMITTED at 2026-09-07T17:57:57.075Z.
Readback verified both values, five null schedules and zero application deployments.
The existing masked Resend key was preserved. Applied settings do not establish runtime readiness.

Next ordered preparation: review source/build
settings with no deployment; finish scoped secret/DB and resource-control proposals; approve
their concrete operations; then proceed to the separately approved migration and rollout below.
Dashboard/logout-all scope disposition and the initial operator procedure remain open. Candidate
selection alone does not defer those requirements or close CRA-122.

DB roles already exist as NOLOGIN; do not recreate them. LOGIN/secrets and post-migration grants
remain pending. Test sender `onboarding@resend.dev` and the owner-only recipient recorded in
CRA-122 are already approved. Preserve that exact scope; synthetic identity/data creation and
worker/source rollout still require their own gates. The first synthetic operator setup below
is not implemented by `bootstrap_venue`. No scenario has been executed by this synchronization.

## Preconditions and evidence ledger

Before each stage, record its action-time approval, UTC start/end, exact project/environment,
application SHA and deployment IDs. Accepted candidate is `2275cee1ae46da708f33a032229e708c73a966c8`;
recheck acceptance and immutable provider evidence rather than trusting a mutable branch label.
Public origin is `https://web-staging-4268.up.railway.app`, without container port 8080.

Maintain one result row per case below: case ID, status (not run/pass/fail/blocked), actual
observation, non-secret request/job/attempt/provider IDs, expected versus actual counts,
redacted evidence location, limitation and reviewer. Do not convert blocked cases into passes
or omit them from the final required-skip count. A provider deployment marked successful and
an API liveness response are insufficient to establish DB/auth/application readiness.

Capture only allowlisted metadata. Do not save raw HTTP traces, HAR, headers, browser storage,
SQL rows with hashes, provider message bodies, screenshots of credentials, invitation/reset URLs,
MFA secrets/codes or cookies. Disable automated failure screenshots/traces around those screens.
An operator can perform protected UI steps without publishing their values to the evidence ledger.

The existing [Playwright configuration](../../frontend/playwright.config.ts) targets localhost
and the E2E suites mock `/api/v1`. The [local synthetic acceptance test](../../backend/tests/api/test_operations_hardening_acceptance.py)
also directly constructs training/assessment state. Neither is a ready-to-run live staging suite.
Do not point repository pytest or its database fixtures at staging. Use approved browser actions
and separately reviewed, narrowly scoped diagnostic operations against the deployed artifact.

## Initial synthetic identities and content

This is a proposal requiring review and synthetic-data/secret approval before any apply.

1. Confirm migration and runtime grants passed. Reconcile the existing synthetic identity inventory
   by names/counts only before creation; stop on an unexpected collision or partial previous run.
2. Select an owner-controlled approved recipient for the initial synthetic operator and test
   employees. Record recipient approval privately; do not reuse customer identities or real Bacara
   content. Define one synthetic Organization/Location and only the additional isolated fixture
   needed for a genuine cross-tenant denial test. The latter is test evidence, not a second pilot.
3. Review a one-time provider-side transaction creating the initial `User` and active platform
   `AdminAccess` using the existing [identity](../../backend/app/models/identity.py) and
   [auth models](../../backend/app/models/auth.py). A random initial password must enter only through
   an approved secret channel and use the existing [password service](../../backend/app/security/passwords.py).
   Do not put a password or its hash in SQL text, this file, shell history or model-visible output.
   The exact guarded operation and secret input channel remain to be prepared and approved;
   this paragraph is not an executable seed script or authorization to bypass authentication.
4. The existing [bootstrap command](../../backend/app/operations/bootstrap_venue.py) requires an
   already-active Platform Operator even for dry run. It creates Organization, Location, one
   OperationalRole and organization-admin access for that same operator; it does not create the
   first User, password or MFA enrollment. Do not attempt it against an empty identity inventory.
5. Review a non-secret JSON spec matching `BootstrapVenueSpec`: `idempotency_key`,
   `operator_email`, `organization_name`, `location_name`, optional `location_address`,
   `timezone` (`Europe/Kyiv`), `role_code`, `role_name_uk`. Keep the recipient-bearing spec in the
   approved provider context, outside Git. From the deployed backend working directory:

   ```text
   python -m app.operations.bootstrap_venue --spec <approved-provider-local-spec-path>
   python -m app.operations.bootstrap_venue --spec <approved-provider-local-spec-path> --apply --confirm-environment staging
   ```

   First command is dry run; second requires explicit apply approval. Review fingerprint and
   planned scope before apply. Replay the identical approved apply once and prove `existing`
   with the same entity IDs and no duplicates. Do not run any speculative cleanup.
6. Complete actual password login and normal MFA enrollment through the public UI. Do not insert
   an authenticated Session, MFA credential or bypass flag as a shortcut to the auth gate.
7. Create the minimum synthetic menu/training/question inventory through existing Admin flows,
   sufficient for 10-question Practice and 20-question Final. Record the exact proposed content
   counts before apply. Do not seed completed training, eligibility or passing results in place
   of exercising the real journey. UI/API gaps require a separate corrective bounded issue.

## Deployment and permission cases

| ID | Procedure | Required evidence |
| --- | --- | --- |
| D01 | Inspect all nine application roles before rollout and after each deployment. | Same accepted SHA; service/image/deployment IDs; no unintended triggers or premature cron execution. |
| D02 | Run only the separately approved `python -m alembic upgrade head` through migration-runner. | Exactly one controlled successful invocation, exit 0, `0018_job_runtime`, migrator ownership; ambiguous outcome reconciled before any retry. |
| D03 | Inspect post-migration effective role flags, memberships and explicit table/sequence grants. | Runtime cannot create schema objects, own/disable immutable triggers or access migration metadata; migrator/runtime URLs have distinct identities; no administrator credential assigned to runtime. |
| D04 | Exercise allowed runtime reads/writes on approved synthetic objects and a bounded transaction attempting forbidden DDL. | Actual runtime identity succeeds on required DML and receives permission denial on DDL; transaction rolled back. Exact operation reviewed separately before execution. |
| D05 | Start API, worker and cron services only after D02/D03; web last. | API DB-backed session path works, worker readiness/start/shutdown and cron exit evidence; one replica/policy/settings match accepted map. |
| D06 | Inspect networking and actual public origin. | Only web public; API/DB stay private; `/healthz` and `/api/v1/health` HTTP 200; neither alone counts as D05. |

## Browser/API cases

Browser paths below come from [App.tsx](../../frontend/src/app/App.tsx). API routes share the
`/api/v1` prefix from [router.py](../../backend/app/api/router.py). Use the current route/schema
definitions for request payloads and expected contract errors; do not invent payloads from this
summary. Separate browser contexts are required for Admin, employee and isolation scenarios.

| ID | Concrete path/action | Required outcome |
| --- | --- | --- |
| B01 | Load `/login` directly and reload `/admin/employees` as a deep link; inspect `/healthz`, HTML and generated assets. | SPA delivery works; correct cache/security headers; missing asset is 404 and not immutable-cached; API errors are not SPA HTML. |
| B02 | `/login`, `/mfa/enroll`, `/mfa`; API `/auth/login`, `/auth/mfa/enrollment/start`, `/auth/mfa/enrollment/confirm`, `/auth/mfa/verify`, `/auth/session`. | Genuine password/MFA flow, required MFA gate, secure HttpOnly host-only session cookie, expected SameSite, no privileged access before MFA. Record attributes only. |
| B03 | Approved credentialed requests at exact origin plus missing/invalid CSRF, unapproved Origin and anonymous requests. | Legitimate flow passes; forbidden write and cross-origin credential access denied; no mutation on rejected request; no wildcard credentialed CORS. |
| B04 | `/admin/employees`; POST `/organizations/{organization_id}/invitations`, then `/invite` using delivered link. | Invitation creates durable email/job evidence; acceptance creates Pending membership/profile and session; `/employee/pending` exposes no Active-only content. External send approval applies before invitation creation with worker running. |
| B05 | PATCH `/organizations/{organization_id}/employees/{employee_id}`, then POST same path plus `/activate`. | Profile save stays Pending; explicit activation alone makes Active; zero-content state truthful; Role/Location controlled by Admin. |
| B06 | `/admin/menu`, `/admin/content`, `/admin/questions`, then `/employee/menu` and `/employee/learning`. | Synthetic content reviewed/published; required assets/question readiness pass; assignments and learning completion arise from normal behavior; Draft has no employee effect. |
| B07 | `/employee/practice`; API `/me/training/practice` and `/me/training/practice/attempts`. | Actual ten-question attempt, final-only feedback and >=40% qualifying eligibility; repeat/idempotent writes do not duplicate effects. |
| B08 | `/employee/final-exam`; API `/me/training/final-exam` and `/me/training/final-exam/attempts`. | Fixed 20-question snapshot, no early correctness leakage, explicit finish and grade once; >=70% passing result/certification. Exercise replay and competing/stale device denial without corrupting state. |
| B09 | `/admin/results`, `/admin/results/:employeeId`, `/admin/attention`. | Correct immutable result/history; Attention workflow does not rewrite source result; assessed employee cannot inspect another employee's private results. |
| B10 | `/forgot-password`, `/reset-password`, `/mfa/recovery`; API `/auth/password/forgot`, `/auth/password/reset`, `/auth/password/change`, `/auth/mfa/recovery/verify`, `/auth/mfa/recovery-codes/regenerate`, `/auth/logout`. | Approved reset delivery; token/recovery replay denial; password/MFA/session revocation behavior matches contract. Never retain reset links or recovery material in evidence. |
| B11 | Employee `/disable`, `/reactivate`, `/pause`, `/resume` under the organization employee API path. | Disabled access denied; identity/results/history retained; reactivation and pause/resume preserve the accepted state semantics. |
| B12 | `/admin/audit`, `/operator/jobs`, `/operator/jobs/:jobId`, `/operator/audit`; API `/operator/jobs`, `/operator/jobs/{job_id}`, `/operator/jobs/{job_id}/retry`, `/operator/audit-events`. | Tenant-scoped audit, MFA-protected operator reads/retry, bounded reason/idempotency; non-operator denied and sensitive job payloads absent. |
| B13 | Repeat organization/object reads and writes using the distinct approved synthetic tenant/employee context. | Concrete cross-tenant and cross-employee denial, no side effects and no data disclosure; UI hiding alone is insufficient. |
| B14 | Upload synthetic image through Admin flow from real origin and download through authorized employee flow. | Presigned FormData POST, API metadata confirmation and signed GET work; exact-origin CORS; anonymous/expired access denied; no credentials in frontend. |

## Worker and scheduled-task cases

Read [background job services](../../backend/app/services/background_jobs.py),
[maintenance](../../backend/app/services/maintenance.py) and [cron entry point](../../backend/app/cron.py).
There is no public lease-manipulation API. A reviewed provider-side diagnostic using existing
services is needed for controlled lost-lease evidence; do not add a debug endpoint or change the
production worker command. Review exact synthetic job IDs and worker coordination before apply.

| ID | Procedure | Required outcome |
| --- | --- | --- |
| J01 | One approved safe non-email job through real worker; capture job/attempt lifecycle. | Pending -> processing -> completed; claimed identity, increasing heartbeat, one attempt outcome and correlation. A job too fast to observe heartbeat does not prove heartbeat. |
| J02 | Controlled synthetic lease: `claim_next_job`, `heartbeat_job`, reviewed stale recovery, then old owner's `complete_job`. | Old heartbeat returns false and old completion raises `LostJobLeaseError`; old attempt cannot finalize or create domain/provider effects; rightful owner can complete once. Exact diagnostic and worker pause/resume remain separately reviewed. |
| J03 | Graceful shutdown after a safe controlled unit of work and approved restart. | No crash loop, leaked connections, duplicate work or abandoned unbounded execution; identify exact deployment and signal evidence. |

Run each existing CLI below twice within the same relevant UTC window, away from its boundary.
The CLI has no `--now` argument. If a fixed-time diagnostic is needed, separately review calling
`run_cron_task(task=..., now=...)`; do not invent CLI flags or change service code.

| ID | Existing command | Same logical bucket and evidence |
| --- | --- | --- |
| C01 | `python -m app.cron stale-jobs` | Direct stale recovery, not a queued bucketed job: use the same approved stale job set and cutoff; second run creates no additional recovery/attempt/domain effect. |
| C02 | `python -m app.cron attempt-expiry` | Same UTC hour; same `attempt-expiry:` job identity, one expiry effect after worker processing. |
| C03 | `python -m app.cron retake-deadlines` | Same UTC hour; same `retake-deadlines:` job identity and no duplicate projection. |
| C04 | `python -m app.cron security-cleanup` | Same UTC date; same `security-cleanup:` job identity; reviewed synthetic expired records only, expected retention preserved. |
| C05 | `python -m app.cron audit-retention` | Same UTC date; same `audit-retention:` job identity; scheduler uses `dry_run=False`, so deletion scope needs explicit review/approval before worker execution. |

Require two exit-0 CLI executions per command (10 invocations), engine disposal, and post-worker
effects/counts for queued tasks. Scheduler exit 0 proves enqueue/reuse, not successful job handling.
Keep concurrent scheduled invocations out of the test window. Record restoration of each approved
schedule; no automatic cleanup/delete after acceptance. Do not age or delete unrelated records.

## Email, observability and final decision

| ID | Procedure | Required outcome |
| --- | --- | --- |
| E01 | Approved invitation to approved staging recipient through normal app and worker. | Provider acceptance and delivery evidence tied to application job/delivery ID; mailbox delivery confirmed without copying link/body. |
| E02 | Approved password reset through normal recovery flow. | Delivery evidence plus real reset success and expected token/session security behavior. |
| E03 | Reviewed controlled retry of the same application delivery identity within provider idempotency retention. | Stable application-derived provider idempotency; no duplicate email or domain effect. A fresh resend is token rotation/new delivery, not a same-delivery retry test. Never fake a provider outage or force a failed-job state without an exact approved method. |
| O01 | Correlate selected request -> job -> attempt -> delivery/result using allowlisted IDs. | Redacted logs and audit carry correlation; forbidden fields absent from reviewed sinks. Optional Sentry absence is not a required skip. |
| O02 | Inspect all services and final case ledger after execution. | No unexplained 5xx, crash/restart, wrong SHA, migration error, Critical/High defect, lost-lease finalization, leaked secret or duplicate external effect. |

Final report includes UTC window, all nine application SHAs/deployment IDs, migration invocation
and head, each case's pass/fail/blocked result, actual counts, redacted evidence, runtime limitations,
exact rollback targets and Denys's final decision. Until every required case has direct live
evidence and Denys accepts it, CRA-122 remains open. No previous accepted staging application
artifact exists: preserve DB/bucket on failure and stop later rollout; no blind downgrade/delete.

Load, backup/PITR/asset restore, real Bacara bootstrap, physical venue UAT and production are later
CRA-78 issues and are not silently included in this synthetic staging runbook.

## Documentation checkpoint

Proposed selective boundary: `docs(deploy): define live CRA-122 acceptance procedure`, only this
file and any separately reviewed navigation link. No local commit or index update is implied.
Documentation-only verification: source-path and relative-link existence, CLI/route cross-check,
CRA-78 section 6 coverage, exact diff/whitespace review and value-free content review. Application
tests, live scenarios, migrations, provider calls and sends are not run by this documentation task.
