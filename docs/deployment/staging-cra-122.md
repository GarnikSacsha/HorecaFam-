# CRA-122 Stage 2 — staging execution plan

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

## Configuration preparation checkpoint — 2026-09-08

### Read-only pre-apply audit

Fresh Railway Details summary confirms 34 variable-only changes across the nine expected
services: migration 2, API 8, worker 7, five cron services 3 each, web 2. The web-only diff
was expanded and confirms PORT=8080 and API_UPSTREAM=http://api.railway.internal:8000.
Other service diffs were not expanded because this UI renders variable values directly.
Masked inventories and six graph edges support runtime-reference wiring, not secret validity.

All nine Settings pages were inspected: no connected source; Dockerfile builder/path;
backend root /backend and web root /frontend; expected role commands; no pre-deploy hook;
all five cron schedules absent; migration/cron restart NEVER and API/worker/web On Failure
with three retries; API /api/v1/health and web /healthz. Web has no start override and uses
its Docker CMD. Its public domain targets port 8080; CDN caching is off, with no edge rules.
Every inspected replica limit remains 8 vCPU / 8 GB. These are ceilings, not consumption.
An initial migration region warning disappeared after loading; the settled UI showed Amsterdam
and one replica, so no region defect or corrective mutation is inferred from the transient UI.

Disposition: configuration preparation only, NOT READY TO DEPLOY. Missing API cryptographic
keys and storage metadata/credentials, worker signing-key references, unsupported source-binding
guarantee, resource controls and untested DB credentials remain blockers. Stored password
encoding, actual role identity, reference resolution and private connectivity require a
secret-safe connection check; a masked value is not proof. Migration, runtime grants and live
acceptance remain unexecuted. This audit changed no provider settings, secrets or source code.

### Runtime connection references completed

After Denys saved the API runtime DATABASE_URL, masked UI readback showed nine API variables
and 28 pending changes. The agent added DATABASE_URL=${{api.DATABASE_URL}} to worker and each
of the five existing cron services. Each target was checked before adding the missing name;
post-save masked readback and graph reference edges confirmed all six references target API.
The final pending count is 34: migration 2, API 8, worker 7, each cron 3, web 2.
No secret value, resolved URL or password encoding was read; no login was tested.
No Apply/Deploy action ran. This supersedes the earlier 27-change count and runtime-entry
next step below. Remaining configuration: application cryptographic keys and scoped storage
metadata/credentials, followed by masked review and controlled application of settings.

Denys requested completion of the available preparation before his next participation.
Scope: staging variable preparation in existing services, read-only provider checks and
this documentation checkpoint. No source binding, deployment or non-test migration.

Fresh UI readback confirms the owner-added migration-runner DATABASE_URL exists and is
masked. It is staged, not applied or connection-tested. Its secret value and encoding were
not inspected. The earlier unsaved-template checkpoint below is superseded.

The agent added 26 non-secret settings through the service Variables UI, preserving existing
variables. Railway now shows 27 pending changes including the owner's DATABASE_URL:

| Service | Newly staged non-secret values | Pending changes including owner input |
| --- | --- | --- |
| migration-runner | APP_ENV=staging | 2 |
| api | APP_ENV=staging; LOG_LEVEL=INFO; CORS_ALLOWED_ORIGINS=["https://web-staging-4268.up.railway.app"]; SESSION_COOKIE_SECURE=true; SESSION_COOKIE_SAMESITE=lax; STORAGE_REGION=auto; PORT=8000 | 7 |
| worker | APP_ENV=staging; LOG_LEVEL=INFO; PUBLIC_APP_URL=https://web-staging-4268.up.railway.app; WORKER_ID=horeca-staging-worker; WORKER_IDLE_SECONDS=1; WORKER_HEARTBEAT_INTERVAL_SECONDS=15 | 6 |
| cron-stale-jobs | APP_ENV=staging; LOG_LEVEL=INFO | 2 |
| cron-attempt-expiry | APP_ENV=staging; LOG_LEVEL=INFO | 2 |
| cron-retake-deadlines | APP_ENV=staging; LOG_LEVEL=INFO | 2 |
| cron-security-cleanup | APP_ENV=staging; LOG_LEVEL=INFO | 2 |
| cron-audit-retention | APP_ENV=staging; LOG_LEVEL=INFO | 2 |
| web | PORT=8080; API_UPSTREAM=http://api.railway.internal:8000 | 2 |

API's existing STORAGE_ADDRESSING_STYLE=virtual was preserved; its raw editor contained no
secrets. JSON-mode readback verified the CORS list encoding before save. Worker already had
EMAIL_FROM_ADDRESS and sealed RESEND_API_KEY; neither was edited or revealed. Secret-bearing
service raw editors were not opened. Each save was checked through masked variable names
and the pending-change count. No Apply/Deploy action was performed.

API Settings freshly shows private api.railway.internal with IPv4/IPv6, no public domain,
EU West (Amsterdam), one replica, Dockerfile builder, /backend root, Dockerfile path,
python -m app.api_server, /api/v1/health and On Failure with three retries. These settings
match the prepared execution path; they do not prove a running build or network connection.
Replica limits are still 8 vCPU / 8 GB; no resource cap was changed. The agreed USD 20 budget
is not an applied spending cap, and sizing remains a pre-rollout gate.

Railway support was checked again: the thread is open and has no technical solution;
the bot records a community bounty. No new message or bounty action was submitted.
The source-binding guarantee remains unresolved.

### Next secret-entry and execution boundaries

1. Denys privately adds API DATABASE_URL for horeca_staging_runtime, with URL-encoded password.
   It must not reuse the migration-runner URL. After masked save, wire worker and five cron
   DATABASE_URL values by a service reference to the API runtime connection.
2. API still needs MFA_ENCRYPTION_KEYS, AUTH_THROTTLE_HMAC_KEY, INVITATION_TOKEN_HMAC_KEYS,
   PASSWORD_RESET_TOKEN_HMAC_KEYS and scoped storage metadata/credentials. Worker needs the
   same invitation/reset key sets by reference. Do not create dummy secret values.
3. Resolve source delivery and resource limits, review the complete staged inventory with
   secrets masked, then apply only the reviewed configuration without deploying.
4. A separately authorized pinned migration and credential connection check must succeed
   before grants/runtime startup. Initial operator identity/password and MFA, storage/email
   smoke and final synthetic acceptance remain subsequent gates.

Documentation boundary: this checkpoint plus the ownership update in
staging-acceptance-cra-122.md. Verification: focused source/config and UI readback,
git diff --check and unchanged Git index. No application tests apply to this configuration
preparation; no passed runtime test is claimed. No code, API or database contract changed.

## Database continuation — verified 2026-09-08

### Latest checkpoint: role LOGIN enabled on 2026-09-08

After Denys entered passwords privately and authorized continuation, a boolean-only
catalog check confirmed passwords exist for both staging roles. No password values or
hashes were returned. A guarded DO block in psql then enabled LOGIN for both roles.
Its preconditions checked the database name, password presence, previous NOLOGIN state
and unprivileged role flags. psql returned DO successfully.

Postflight returned two rows: LOGIN, CONNECT and public USAGE true for both;
public CREATE true only for horeca_staging_migrator; memberships zero for both.
SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS and INHERIT remained false.
The earlier Data editor attempt failed with a syntax error near its appended LIMIT;
the successful operation ran through Console/psql instead.

The migration-runner Variables form now contains an unsaved DATABASE_URL template using
the migrator role and postgres.PGHOST, postgres.PGPORT and postgres.PGDATABASE references.
Those variable names were verified without revealing secret values. The password
placeholder must be replaced privately with a URL-encoded password before saving.
No connection variable was saved, no application-role login was tested, and no migration
or deployment ran. The NOLOGIN inventory and password/LOGIN steps below describe the
earlier checkpoint; the next pending step is connection configuration.

Canonical sources found in Linear:
[CRA-10](https://linear.app/craftspacee/issue/CRA-10/design-database-schema-and-entity-relationships),
[Database Design — BASE ERD + CURRENT OVERRIDES](https://linear.app/craftspacee/document/database-design-horeca-v01-base-erd-current-overrides-7c46dc74c14d),
and CRA-122's accepted staging decision/provisioning record.
The design is approved; historical ERD tables are not a request to implement them again.
Current candidate remains fafec73 / 0019_auth_security_budgets.

Two catalog-only SELECTs executed successfully through Railway Database > Data in the
existing staging PostgreSQL service. First query returned two role rows; second returned
one database/schema summary row. No customer rows, credentials or password hashes were queried.

| Observed item | Fresh result |
| --- | --- |
| Database/server | railway; PostgreSQL 16.15 |
| Existing roles | horeca_staging_migrator; horeca_staging_runtime |
| LOGIN / INHERIT | false / false for both |
| SUPERUSER / CREATEDB / CREATEROLE / REPLICATION / BYPASSRLS | false for both |
| Role memberships | 0 for both |
| Database CONNECT / public USAGE | true / true for both |
| public CREATE | migrator true; runtime false |
| public relations (tables, sequences, views, foreign tables) | 0 |
| public functions | 0 |
| public.alembic_version exists | false |

The deployment database exists; the application's public schema is not migrated.
This is fresh evidence, superseding the September 5 role/schema inventory date.
It is not evidence of credential readiness or a successful runtime connection.

### Exact next operation, prepared but not executed

1. Through the existing PostgreSQL Console, Denys enters independent random passwords using
   masked psql prompts: `\password horeca_staging_migrator`, then
   `\password horeca_staging_runtime`. The agent must hand off before credential entry;
   never include password values or hashes in SQL text, chat or recorded output.
2. After password entry and explicit access-change authorization, the SQL delta is only:
   `ALTER ROLE horeca_staging_migrator LOGIN;`
   `ALTER ROLE horeca_staging_runtime LOGIN;`
   Recheck both role rows and retain all other flags/memberships/ACLs. Do not create roles again.
3. Configure a migrator connection only for migration-runner, and a distinct runtime connection
   for API, worker and five cron services through the secret UI. Web receives neither.
   Use the verified private database host; no public proxy or superuser application connection.
   Exact secret settings must be reviewed without printing values before applying.
4. The separately authorized migration runner creates the application schema through 0019.
   Reconcile actual tables/sequences/owners/functions/triggers with the pinned migrations.
   Grant runtime access only to the reviewed application-object inventory, excluding
   alembic_version and ownership/DDL/grant options. There are no tables to grant yet.
5. Create the first operator only after migration and grants. The current User model uses
   email_normalized (not the older ERD's conceptual email label); platform AdminAccess has
   organization_id null. Reuse PasswordManager and real MFA enrollment. No seed was executed.

Documentation boundary: this section in staging-cra-122.md and the matching CRA-122 evidence
record. Validation: two successful catalog queries / three result rows, focused source review,
and git diff --check. No schema redesign, application edit, migration, credential/access change,
commit or deployment occurred. The remaining external operations retain their execution gates.

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

## Build/start settings applied — 2026-09-07

Denys confirmed the nine-service build/start package. Patch
`fea986f8-c963-41f7-9b13-49053be89380` is COMMITTED at 2026-09-07T19:40:13.612Z with
skipDeploys=true; exact normalized delta: 39 fields. Postflight confirmed 84 instance fields
and nine DOCKERFILE builder values in saved config. ServiceInstance builder still reports
RAILPACK, so actual Dockerfile use remains a later build-evidence gate. Nine services still
have repo null, hasEverDeployed false and zero deployments; no push triggers and five disabled
cron schedules. See the [execution detail](cra-122-source-build-preparation.md).
Source binding remains unperformed pending its autodeploy mechanism check. No application
tests, Git commits, migration, secrets or email sends accompanied this settings operation.

## Source/build package prepared — 2026-09-07

The [reviewable preparation package](cra-122-source-build-preparation.md) contains separate
nine-service JSON drafts for build/start policy and immutable source binding, fresh metadata
and trigger evidence, verification and rollback boundaries. No draft was staged or applied.
The build draft is independently reviewable. Source application awaits proof that push
autodeploy stays disabled during binding; branch null and skipDeploys are not assumed to
provide that guarantee. Single-region/replica query fields are null and need reconciliation
before rollout. Accepted candidate and existing seven-change committed package are preserved.

## Approved seven-change package applied — 2026-09-07

Denys approved five cron schedule removals plus application of the two pending non-secret
variables. Exact pending inventory and original schedules were checked before mutation;
the five removals were merged into the existing patch. Exact seven-change comparison passed
before one `environmentPatchCommitStaged(skipDeploys: true)` invocation.
Patch `ee4d02d2-388d-46cd-a7be-49f30046b42c` is COMMITTED with
`appliedAt=2026-09-07T17:57:57.075Z` in the existing staging environment.

Readback passed: API `STORAGE_ADDRESSING_STYLE=virtual` and worker
`EMAIL_FROM_ADDRESS=onboarding@resend.dev` match in the committed patch; all five cron
schedules are null; all nine application services have null latest deployment, zero active
deployments and no source. PostgreSQL remains SUCCESS with one active deployment.
The existing sealed Resend key was not changed. Original schedules remain in the restoration
matrix below; restore each only after its separately approved successful first run.

Verification detail: an initial check expected the nonexistent status APPLIED and failed.
Live enum inspection established COMMITTED as the successful terminal status; corrected
read-only checks passed without repeating the mutation. Earlier read-only command quoting
and schema-fetch errors were resolved before staging. No application tests were rerun.
No source binding, migration, DB/secret mutation or send occurred. Source/build preparation
for accepted candidate `2275cee1ae46da708f33a032229e708c73a966c8` is next; earlier pending
and schedule-active statements below are historical. This record remains uncommitted.

## Accepted candidate — 2026-09-07

Denys explicitly accepted `2275cee1ae46da708f33a032229e708c73a966c8` for all nine
staging application services. Local main and origin/main still match. Candidate-pending
wording in earlier dated checkpoints is superseded. The decision is recorded in CRA-122
and its canonical Stage 2 document; CRA-122 remains In Progress.

Next proposed provider boundary: temporarily clear the five cron schedules listed in the
restoration matrix and apply that exact settings batch with `skipDeploys: true`. Because
two approved non-secret variables are already pending, the reviewed batch must explicitly
include their application as well: API `STORAGE_ADDRESSING_STYLE=virtual` and worker
`EMAIL_FROM_ADDRESS=onboarding@resend.dev`. Expected diff: five schedule removals and two
variable additions, with no secret edits. Reconcile the actual pending inventory first;
any additional change requires a revised review. Verify five unset schedules and zero
application deployments afterward. This operation is proposed, not yet authorized.

Source/build binding follows only after schedule suspension is verified. Secret/DB
operations, resource controls, migration, rollout, initial operator preparation and
Dashboard/logout-all scope disposition retain their existing gates. Candidate selection
does not close these gates or mark corrective issues Done. No Git commit is authorized
by this decision; the documentation boundary is this file, the live acceptance runbook
and STATUS.md, checked for matching SHA, links, case preservation and whitespace.

## Two approved settings staged — 2026-09-07

Denys explicitly approved both entries from the proposal below. Saved through the Railway
staging UI: API `STORAGE_ADDRESSING_STYLE=virtual` and worker
`EMAIL_FROM_ADDRESS=onboarding@resend.dev`. The final Details panel shows exactly two changes,
one variable for each target service, with both non-secret values read back successfully.
No Apply/Deploy action was performed.

At entry, the UI showed no staged-change banner and worker already contained a masked
`RESEND_API_KEY`. After the first addition, Details listed only `EMAIL_FROM_ADDRESS`; after
the second, it listed exactly the two approved variables. The existing key was neither
revealed nor edited and is not part of this pending inventory. Its earlier description as
a staged change is historical; this check does not establish its runtime use or scope.

Post-change read-only CLI verification covered all ten services: PostgreSQL remains SUCCESS
with one active deployment; all nine application services still have null latest deployment,
zero active deployments and no source. Application code and contracts are unchanged; no
application tests were rerun for this provider-settings step. This evidence is an uncommitted
documentation update. The next step remains the separate Stage 2 candidate/settings and
secret/DB readiness decisions; this approval did not authorize applying the pending batch.

## Latest preparation after CRA-125 publication — 2026-09-07

The explicitly authorized ten-commit fast-forward is published through
`2275cee1ae46da708f33a032229e708c73a966c8`. Direct remote readback matches local main. Propose
this exact SHA for the nine application roles; the earlier `e18af71` proposal and failed local
coverage descriptions below are historical. Candidate acceptance and deployment remain separate.
CRA-125's unchanged full PostgreSQL gate passed 809 tests, 0 failed/skipped: statements
11408/12135 (94.01%), branches 2041/2538 (80.42%), critical aggregate 1293/1443 (89.60%).
All nine pre-commit focused suites and Ruff/mypy checks passed. No fresh application suite
was run as part of publication or this planning update.

Fresh read-only preflight used existing Railway CLI with explicit project
`04320f63-ab40-426f-ab35-02fcb365c3b8` and staging environment
`d8e64109-9863-4faa-a45e-f072adb3cfac`. The workspace is not CLI-linked; explicit IDs worked,
and no link/configuration was created. All ten service IDs match the matrix. PostgreSQL has
latest deployment SUCCESS, one active deployment and one replica. Each of the nine application
services has null source/latest deployment, zero active deployments and null replica count.
The five cron schedules still match the recorded matrix. No variables, secret values or opaque
deployment metadata were displayed or stored in this evidence. The pending-change count was
null, so it is unavailable, not evidence of an empty pending batch.

The next bounded provider proposal remains only these staged non-secret entries:

| Service | Variable | Value |
| --- | --- | --- |
| api — 785ae5f7-9052-4a1b-92ea-e8524236de97 | STORAGE_ADDRESSING_STYLE | virtual |
| worker — 5028af74-ea48-4c31-97d7-042ae0c5836d | EMAIL_FROM_ADDRESS | onboarding@resend.dev |

Before writing, inspect the actual pending inventory without revealing sealed values and
preserve the owner's staged Resend key. Read back only these two non-secret entries and confirm
the services still have no deployment. This proposal does not approve committing/applying a
combined pending batch, source binding, schedule changes, DB LOGIN, migration or email sends.
Execute only after explicit approval of this two-entry provider step. If the interface would
automatically apply unrelated pending changes or create a deployment, stop before writing.

Remaining Stage 2 decisions: exact candidate/formal corrective acceptance, Dashboard/logout-all
scope disposition, scoped secret/DB preparation, first synthetic operator, project-specific
cost controls and live storage/email/runtime acceptance. Passing local coverage removes the
measured coverage deficit; it does not close these independent gates. This local planning
update and publication evidence remain uncommitted follow-up documentation.

## Current checkpoint — 2026-09-07

Denys authorized repository/Linear reconciliation after the audit. This is documentation and planning under CRA-122, not new product implementation, local-commit, push or provider-execution authorization.

Published main: `e18af71f89d587b1cb6b472cf189e67dfa8102a0`; local main and the direct GitHub ref match. This includes CRA-123 `ec27d19` and CRA-124 `e18af71`. Both corrections are implemented, locally verified and published; formal acceptance disposition remains explicit and is not inferred from push. The current proposed all-role staging candidate is `e18af71`, pending exact Stage 2 acceptance. Historical CRA-119 endpoint remains `2644b796`; Alembic head remains `0018_job_runtime`.

CRA-121 is accepted and Done. CRA-122 Stage 1 is complete; Stage 2 remains open. The 2026-09-07 read-only Railway status check showed PostgreSQL Online and nine application services Offline. Last SQL/secret/storage inventory remains dated 2026-09-05: browser psql works; both DB roles exist as NOLOGIN/NOINHERIT with reviewed CONNECT/USAGE and CREATE only for migrator; passwords/LOGIN and post-migration runtime grants remain pending. Do not repeat role creation or SSH-key registration.

Already resolved: GitHub App repository access; USD 20/month project budget (not an applied billing cap); test sender `onboarding@resend.dev` and the owner-only recipient recorded in CRA-122; virtual-host bucket URL style. The owner-entered Resend key is sealed in a staged worker change, not deployed; its recorded Full access scope needs review. Storage addressing-style support is published; propose `STORAGE_ADDRESSING_STYLE=virtual` for API only, without applying it here.

Fresh audit evidence on 2026-09-07: 552 backend tests / 0 failed / 0 skipped in 1324.34s; 72 Vitest tests; 42 Playwright executions (14 scenarios × three viewports); 5 artifact/topology tests; format/lint/types/build and Alembic upgrade/current/no-drift passed. Coverage is 89.22% statements, 67.76% branches, 85.51% combined (rounded to 86%). The predeclared nine-file CRA-77 critical set is 85.19% statements, 64.89% branches, 81.22% combined. Denys approved independent overall statement and branch thresholds of at least 80% on September 7 (CRA-13): statements PASS, branches FAIL. Critical aggregate remains at least 80%. See the coverage closure plan; implementation approval remains separate. The documentation-only follow-up does not rerun or relabel this audit suite.

Coverage follow-up: [bounded closure plan](../testing/coverage-closure-plan.md), prepared only.

Open decisions owned by Denys: approval of the bounded coverage implementation map (the independent 80% statement / 80% branch rule is approved, branch gate currently FAIL); implemented/deferred disposition for the original FINAL API Dashboard and logout-all endpoints; formal CRA-123/124 acceptance and exact Stage 2 candidate/settings approval. Technical preparation still includes cost controls, scoped secrets, DB LOGIN/runtime grants, the first synthetic Platform Operator setup, and real-origin storage/email/runtime acceptance. Local Playwright mocks and SDK signing tests do not prove live providers. Docker HTTP tests were not rerun on 2026-09-07 because the Linux engine was unavailable.

The nine accepted functional slices already include frontend journeys. CRA-19 remains a separate visual track; no new backend slice is required merely to prepare Bacara visuals. Source/settings, secret provisioning, migration, deployment, synthetic writes, load/restore/UAT and production gates remain separate. Existing test-email permission remains valid only for its recorded recipient/sender scope.

The dated material below is preserved history, not a competing current checklist.

## Stage 2 execution proposal — 2026-09-07

### Fresh settings preflight and next small preparation step

The September 7 preparation query selected service IDs/names, source repository, builder,
root/Dockerfile, start/health/restart, schedules, replicas and deployment status only. It did
not request variables, credentials or opaque deployment metadata. All ten returned services
were inspected: PostgreSQL has deployment SUCCESS; all nine application roles have null source,
no latest deployment and `hasEverDeployed=false`. Their builder remains RAILPACK; roots,
Dockerfile and health paths are unset; restart remains ON_FAILURE with 10 retries. Existing
worker/migration/cron commands and all five schedules still match the restoration matrix.
Application replica counts are null, so do not describe one replica as an observed setting.

The next proposed provider step is limited to staging these two non-secret variable changes:

| Existing service | Variable | Proposed value |
| --- | --- | --- |
| api (`785ae5f7-9052-4a1b-92ea-e8524236de97`) | `STORAGE_ADDRESSING_STYLE` | `virtual` |
| worker (`5028af74-ea48-4c31-97d7-042ae0c5836d`) | `EMAIL_FROM_ADDRESS` | `onboarding@resend.dev` |

Target environment: `d8e64109-9863-4faa-a45e-f072adb3cfac` (staging). Review the current pending
change inventory before entry, preserving the owner-entered sealed Resend key. Do not reveal
values or apply a combined pending batch implicitly. This two-variable step does not bind a
source, create a deployment, enable DB login, change schedules or send email. Confirm both
non-secret entries and continued absence of application deployments afterward. It remains an
execution proposal until separately approved; this preparation has changed no provider setting.

Subsequent preparation uses the complete matrix below: suspend schedules before source binding,
apply Dockerfile/start/health/restart settings without deployment, then complete scoped secret and
DB preparation. The accepted 80% branch gate currently fails; candidate acceptance and rollout
remain blocked by that gate and the other recorded prerequisites. Resource ceilings and a
project-specific cost-control method remain unresolved; do not apply a workspace-wide USD 20 cap.

Documentation checkpoint: retain this addition in the existing uncommitted CRA-122 staging-plan
boundary. Verification is the read-only ten-service inventory, comparison with both Dockerfiles
and the existing command matrix, and `git diff --check`; no application test rerun is claimed.

This proposal supersedes earlier unresolved SHA-mechanism and unpublished-source wording.
It is a planning deliverable, pending Denys acceptance and the remaining decisions below.

### Exact source and deployment operation

Remote `main` was verified on September 7 at `e18af71f89d587b1cb6b472cf189e67dfa8102a0`.
Propose that full SHA for all nine application roles, subject to Denys acceptance. GitHub App access is already resolved.
The September 5 read-only Railway schema inspection confirmed `serviceInstanceDeployV2(environmentId: String!,
serviceId: String!, commitSha: String): String!`. Railway's official
[service API documentation](https://docs.railway.com/integrations/api/manage-services)
describes explicit commit selection and rejection of unknown commits.

After each role's deployment approval, call this operation once with the existing staging
environment ID, the role ID from the target matrix and the full accepted SHA. Capture its
returned deployment ID. Do not omit `commitSha`, use Deploy Latest Commit, or upload the dirty
working directory. An ambiguous timeout requires reconciliation of deployment history before
retry; never assume that the request did not create a deployment.

This proves an available selection mechanism, not a completed rollout. For each created
deployment, verify project/environment/service IDs, source commit in the deployment UI,
creation time, status and image identifier where exposed. Store these in a nine-row evidence
ledger. `Deployment.meta` is an opaque scalar in the live schema: do not dump it or environment
configurations into evidence. If the exact commit cannot be verified, stop before later roles.
An explicit source SHA does not guarantee identical image bytes across independent builds.

### Proposed service-setting changes

All rows apply only to the existing staging application service IDs in this document.
Keep the existing Amsterdam placement, one replica, public/private networking and resources.
Do not modify PostgreSQL or the bucket. The USD 20/month project budget is agreed; exact CPU/memory limits and cost controls remain open.

| Setting | API | Worker | Migration | Five cron roles | Web |
| --- | --- | --- | --- | --- | --- |
| Source repository | `GarnikSacsha/HorecaFam-` | same | same | same | same |
| Root / Dockerfile | `/backend` / `Dockerfile` | same | same | same | `/frontend` / `Dockerfile` |
| Builder | Dockerfile | Dockerfile | Dockerfile | Dockerfile | Dockerfile |
| Start | Exact command in matrix below | Exact command below | Exact command below | Each exact command below | Existing Docker CMD |
| Health path | `/api/v1/health` | unset | unset | unset | `/healthz` |
| Restart | ON_FAILURE, 3 retries | ON_FAILURE, 3 retries | NEVER | NEVER | ON_FAILURE, 3 retries |
| Cron schedule during preparation | unset | unset | unset | Clear all five; retain restoration matrix | unset |
| Push-trigger autodeploy | disabled | disabled | disabled | disabled | disabled |
| Serverless | disabled | disabled | disabled | disabled | disabled |

Preparation order: (1) review pending changes, (2) suspend all five schedules and save with
`skipDeploys: true`, (3) verify cleared schedules and zero application deployments, (4) stage
the reviewed source/build/start/health/restart settings and disable source triggers,
(5) inspect the exact staged diff, (6) commit with `skipDeploys: true`, (7) verify nine sources,
zero application deployments and disabled triggers. The schema for
`environmentPatchCommitStaged` and its `skipDeploys` argument was rechecked read-only.
The documented staged workflow is the proposed mechanism; no source-binding mutation has
been tested. Stop if the UI offers an immediate connection/run instead of staged changes.

After successful migration, authorize each terminating cron's first run separately from
restoring its schedule. Restore only that role's original UTC expression after successful
exit and acceptance of its evidence. No migration or API startup may restore schedules implicitly.

### Configuration values and secret ownership

Set backend runtime roles to `APP_ENV=staging`, `LOG_LEVEL=INFO`; migration to
`APP_ENV=staging`. API uses `PORT=8000`, `SESSION_COOKIE_SECURE=true`,
`SESSION_COOKIE_SAMESITE=lax`, and CORS JSON containing only
`https://web-staging-4268.up.railway.app`. Worker uses that same origin for `PUBLIC_APP_URL`,
`WORKER_ID=horeca-staging-worker`, idle 1 second and heartbeat 15 seconds.
Web uses `PORT=8080` and `API_UPSTREAM=api.railway.internal:8000`.
There are no frontend build secrets.

The existing variable matrix defines consumers. Create independent staging credentials only
after secret-operation approval. MFA requires a valid Fernet key encoded as a JSON key list;
HMAC lists require entries of at least 32 characters, and the throttle key at least 32 characters.
Use cryptographically generated keys through the approved secret channel, never chat or files
in this repository. API and worker must receive the same invitation/reset signing key sets.
Cron and migration receive no mail, storage or authentication keys.

The DB separation uses existing `horeca_staging_migrator` and `horeca_staging_runtime`.
Both roles were created and verified NOLOGIN/NOINHERIT on September 5; migrator alone received
schema CREATE. Do not recreate them. The administrator stays outside application services.
LOGIN/password provisioning, actual post-migration table/sequence grants and future-object
reconciliation require their reviewed execution boundary below.
Do not use PostgreSQL administrator references as a substitute. Every migration URL must already
use `postgresql+asyncpg`; provider-side composition must preserve URL encoding.

Storage credentials must be scoped to the existing staging bucket and API only. Verify bucket
ID, endpoint/region and credential scope through provider metadata before entry. Resend needs
an approved sender domain/address and a separately revocable sending key before worker startup.
Approved test recipients and send authorization are separate from configuring those credentials.

### Remaining decisions and acceptance boundary

- Denys: resolve the coverage gate and formal corrective/candidate acceptance; accept the exact
  settings proposal when technical prerequisites below are ready. Budget and test sender/recipient
  are already recorded, not unanswered questions.
- Operator preparation: reviewed LOGIN/secret/grant operations, storage credential scope/CORS,
  first synthetic operator setup, and cost controls within the approved project budget.
- Stage 3 approval: exact reviewed source/settings and secret operations, with no deployment.
- Stages 4–8: retain separate migration, rollout, synthetic-data and email-send approvals.

Do not mark Stage 2 fully accepted while these inputs are unresolved. This September 7 follow-up performs documentation synchronization only, not Railway mutations,
new credentials, DB operations, builds or deployments. September 5 role creation and staged key
entry are completed historical actions, not undone by this statement.
Validation: remote SHA read succeeded; September 5 API evidence confirmed explicit SHA and skip-deploy
arguments; config, Dockerfiles, migration entry point and cron composition were reviewed.
Initial sandboxed CLI network access failed; the read-only network-enabled retry succeeded.

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
| web | `/frontend` | Docker CMD: `caddy run --config /etc/caddy/Caddyfile --adapter caddyfile` | Port 8080; `/healthz` implemented in published CRA-123; candidate acceptance open |

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
| `STORAGE_ADDRESSING_STYLE` | API | Proposed explicit `virtual`, supported by published CRA-124; not applied |
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

The two separate roles exist as documented above. Initial CONNECT/USAGE and migrator CREATE
are verified historical evidence, not runtime DML or LOGIN proof. Finish the exact post-migration
grant review under the separate DB-action gate; do not assign the database administrator.

Worker startup calls `validate_worker_readiness()`: Resend key, sender, public URL and signing
keys are prerequisites for Stage 5. Stage 8 tests delivery later; it cannot postpone configuration
until after worker startup. Synthetic email-producing actions must stay within the already-approved test sender/owner-only
recipient scope; real recipients or broader sends require a new decision.
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


## DB and storage preparation details

### Database preparation and evidence

Keep the existing database and schema layout. The existing roles are
`horeca_staging_migrator` and `horeca_staging_runtime`, created and verified September 5.
Recheck their flags and grants before subsequent execution; do not create them again.

Before preparing the final executable SQL, use an approved private diagnostic connection to
collect only: database name/owner, schema owners/ACLs, application table/sequence/function owners,
role flags and memberships, default privileges, and presence/version of `alembic_version`.
Do not read customer rows, password hashes, connection strings or role passwords. The live
inventory is recorded in the browser SQL sections above; emptiness was verified from catalogs,
not inferred from offline services.

For the confirmed empty staging application schema, the proposed administration sequence is:

1. Reverify the two existing NOLOGIN/NOINHERIT roles, all privileged flags false and no
   runtime membership in migrator/owner/admin roles. Their creation is already complete.
2. Reverify existing CONNECT/USAGE and CREATE only for migrator. The September 5 grant step
   is complete; any changed ACL requires review, not blind replay of historical SQL.
3. Enable LOGIN and provision separate random passwords only through the approved secret channel.
   Assign the migration URL only to migration-runner and runtime URL only to API/worker/cron.
4. Run the separately approved migration as migrator, so application objects are owned by it.
   Do not apply generic ownership changes to existing objects if inventory was nonempty.
5. After migration, grant SELECT/INSERT/UPDATE/DELETE on the explicit application-table inventory
   to runtime, excluding `alembic_version`. Grant USAGE on only sequences actually required.
   No TRUNCATE, REFERENCES, TRIGGER, schema CREATE, ownership or grant option.
6. Verify function/trigger requirements from the resulting inventory. Runtime must not own or
   disable the append-only triggers. Do not blindly revoke function execution without evaluating
   the trigger dependencies. Future migrations require a reviewed grant reconciliation.
7. Prove role flags, memberships and effective object permissions with PostgreSQL privilege
   functions before runtime deployment. Exercise actual synthetic allowed/denied paths during
   the separately approved staging acceptance; catalog assertions alone are not an integration pass.

Historical CONNECT/USAGE/CREATE grants below already exist. Only the table/sequence shapes are
future post-migration proposals; identifiers remain intentionally unresolved. Do not run this
illustrative block as a script:

```sql
GRANT CONNECT ON DATABASE "<verified_database>" TO horeca_staging_migrator, horeca_staging_runtime;
GRANT USAGE ON SCHEMA public TO horeca_staging_migrator, horeca_staging_runtime;
GRANT CREATE ON SCHEMA public TO horeca_staging_migrator;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."<reviewed_application_table>"
  TO horeca_staging_runtime;
GRANT USAGE ON SEQUENCE public."<reviewed_required_sequence>" TO horeca_staging_runtime;
```

This is not an apply script. Avoid broad grants on every table, which would include migration
metadata. Default privileges are owned by the object-creating role and affect future objects
only; they do not repair existing grants. This proposal uses explicit post-migration grants
until a complete future-object policy is reviewed. Sources:
[PostgreSQL 16 GRANT](https://www.postgresql.org/docs/16/sql-grant.html) and
[default privileges](https://www.postgresql.org/docs/16/sql-alterdefaultprivileges.html).

### Storage wiring and browser acceptance

Only API receives bucket credentials. Proposed references for existing `learning-assets` are:

| Application variable | Provider reference |
| --- | --- |
| `STORAGE_BUCKET` | `${{learning-assets.BUCKET}}` |
| `STORAGE_ENDPOINT_URL` | `${{learning-assets.ENDPOINT}}` |
| `STORAGE_REGION` | `${{learning-assets.REGION}}` |
| `STORAGE_ADDRESSING_STYLE` | Explicit `virtual` after settings approval |
| `STORAGE_ACCESS_KEY_ID` | `${{learning-assets.ACCESS_KEY_ID}}` |
| `STORAGE_SECRET_ACCESS_KEY` | `${{learning-assets.SECRET_ACCESS_KEY}}` |

Verify the resource/environment IDs and reference resolution without displaying values.
The S3 bucket name is the provider BUCKET value, not its display name. Verify the provider's
required URL style before execution. September 5 metadata returned virtual-host; published
CRA-124 supports an explicit addressing-style override. Propose `STORAGE_ADDRESSING_STYLE=virtual`. Credentials remain provider-owned and absent from frontend build variables.

The code uses `generate_presigned_post`, browser FormData POST, server `head_object`, and
presigned GET. Review bucket CORS for the exact staging browser origin and these operations.
After a separate configuration/data approval, prove an authorized synthetic image upload,
metadata/size/type confirmation and protected download from the real browser origin; also
prove anonymous access denial and expired-signature rejection. Do not replace POST with PUT
inside this planning issue if a provider compatibility issue appears.

Railway private buckets are authenticated object storage; they are not private-network-only
services. Preserve HTTPS and signed access, and account for service egress. Verify available
credential permission granularity rather than claiming an unobserved custom IAM policy.
References: [bucket variables and access](https://docs.railway.com/storage-buckets),
[bucket networking/billing](https://docs.railway.com/storage-buckets/billing).
This is configuration/test preparation, not a live bucket or CORS verification.


## Remaining closure and approvals

| Item | Current fact / next closure |
| --- | --- |
| Published corrections | CRA-123 ec27d19 and CRA-124 e18af71 are published; formal acceptance disposition remains explicit |
| Artifact | Propose `e18af71f89d587b1cb6b472cf189e67dfa8102a0` for all nine roles; exact candidate approval remains open |
| Coverage / original API scope | Audit reports separate metrics and Dashboard/logout-all gaps; Denys decision, no silent threshold/scope change |
| DB | Roles and initial grants exist; LOGIN/password channel, post-migration DML grants and actual denial evidence remain pending |
| Storage | Virtual-host metadata verified; code support published; API-only setting/references and live-origin CORS/POST/GET remain pending |
| Email | Sender onboarding@resend.dev and owner-only recipient approved; worker key sealed/staged; Full access scope and runtime setup remain to review |
| Cost | USD 20/month project budget agreed; per-service limits/monitoring and overrun response remain pending; no global workspace cap |
| First synthetic operator | Bootstrap requires an existing active operator; exact initial identity/secret setup is still a review deliverable |
| Source preparation | Reviewed skip-deploy mechanism and cron suspension/restoration; inspect current staged delta and reverify mechanism before an approved apply |
| Live evidence | All deployment/DB/browser/worker/cron/email cases remain unexecuted; use the live acceptance runbook |
| Git | This documentation map is uncommitted; local commits and push need explicit authorization |

The full [live acceptance runbook](staging-acceptance-cra-122.md) contains the synthetic setup
prerequisite and D/B/J/C/E/O evidence cases. Never point destructive pytest fixtures at staging.
The [audit evidence](../testing/repository-audit-2026-09-07.md) records exact local checks,
the two documentation checkpoint boundaries and the unresolved coverage decision.

## Documentation verification

This September 7 update is documentation-only and reuses the completed September 7 audit results.
Check source routing, links, configuration names, service IDs/commands, safe content and exact
inventory/diff. Preserve prior user-authored planning and dated evidence below. No local commit,
push, provider change or new application-suite run is implied.

## Provider references reviewed on 2026-09-04

- [Railway monorepo roots](https://docs.railway.com/deployments/monorepo).
- [Railway GitHub autodeploy controls](https://docs.railway.com/deployments/github-autodeploys).
- [Railway terminating cron jobs](https://docs.railway.com/cron-jobs).
- [Resend idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys).

These explain platform behavior; they do not prove the current account's settings or permissions.


<details>
<summary>Historical preparation and approvals through September 5 — do not execute as a current checklist</summary>

Earlier next-action statements, role-creation SQL, SHA proposals and commit authorizations below
are retained for traceability. The current checkpoint and plan above supersede their status.

## Storage URL-style preflight — 2026-09-05

Live GraphQL requested only `urlStyle`, `endpoint` and `region` for the exact existing bucket;
no access-key or secret-key fields were selected. Result: `virtual-host`,
`https://t3.storageapi.dev`, `auto`. Settings UI confirmed Amsterdam and exposed no CORS editor.

Independent offline inspection of the actual Boto3 factory with fake credentials showed
path-style POST/GET URLs for a custom endpoint. The factory currently passes no addressing-style
configuration. Therefore the required virtual-host behavior must be resolved before storage
acceptance. This is not a live authenticated upload failure: no object or credential was used.
A separate bounded correction/review is required if application or packaged configuration changes.
Do not replace the existing presigned POST contract with PUT as a workaround.

## Resend key staged and sealed — 2026-09-05

Denys confirmed no owned HoReCa domain and that the newly created Resend key `HorekaFam` was
saved privately. Its dashboard metadata showed Full access and no activity; no key value was
read. Denys entered `RESEND_API_KEY` directly into the existing staging worker Variables form
and confirmed Add. Railway showed one staged worker change. Seal was confirmed; Show/Copy and
Seal/Promote actions disappeared. The value was never revealed or copied by the agent.

This is a staged secret, not a deployed worker configuration or proof of successful sending.
No Deploy was clicked. Review the key's broader-than-required Full access permission before
accepting provider scope. Proposed temporary sender is `onboarding@resend.dev`, restricted by
Resend to the owner's account mailbox; sender/recipient/send approval remains pending.

The [live acceptance runbook](staging-acceptance-cra-122.md) records the required unexecuted cases.

## Remaining execution decisions — 2026-09-05

Denys set a maximum monthly HoReCa staging budget of USD 20. This is the project budget,
not an applied Railway hard limit. Read-only CLI checks found no workspace compute limit and
16 projects sharing the workspace. Railway's compute hard limit stops all workspace workloads;
setting USD 20 globally would affect unrelated projects and is not authorized by this project
budget. Agent usage has a separate USD 5 cap. Resource caps and the project cost-control method
still need resolution before rollout; do not promise a guaranteed USD 20 bill from replica caps.

The owner requested one simple setup question at a time. Domain ownership is the next input;
sender and test recipient must then be resolved. Do not repeatedly bundle these with budget.

Independent preparation review also identified two acceptance prerequisites:
- The empty DB needs a reviewed first synthetic Platform Operator setup: `bootstrap_venue`
  requires an existing active operator even for its dry run. It does not create that first user.
- Existing frontend Playwright suites use localhost and mocked API routes. Their passing counts
  cannot prove the real staging-origin acceptance matrix. Execute the actual CRA-78 live journey.

Password handling route under review: owner enters two saved independent passwords directly
through psql `\password` masked prompts and the Railway secret UI. The agent supplies only
commands and reference expressions. Never transfer a generated password as a CUA argument.
LOGIN enablement, secret settings, source binding, migration and rollouts retain their explicit
action-time decisions. No password provisioning has occurred.

## Approved DB roles created — 2026-09-05

Denys explicitly approved creating the two NOLOGIN roles and their reviewed grants. The exact staging project/environment/PostgreSQL service was verified in the browser. Database > Data did not confirm the DO block; a subsequent SELECT returned zero roles. The existing service Console connected successfully, and psql executed the guarded atomic DO statement once with PostgreSQL confirmation `DO`. This browser-console path works without local SSH port 22.

Post-apply catalog verification passed for both roles: NOLOGIN/NOINHERIT and all privileged flags false, no memberships, database CONNECT and schema USAGE true for both, database CREATE false for both, public schema CREATE true only for horeca_staging_migrator and false for horeca_staging_runtime. Exactly two rows returned; 12 expected boolean checks passed, zero failed/skipped. psql was closed after verification.

No passwords were provisioned or inspected; login remains disabled. No application tables, migration, deployment, public DB proxy or email send was performed. Next: prepare separately approved secret provisioning/login enablement and migration-runner configuration; migration retains its own approval. Budget, sender/recipients and remaining Stage 2 gates stay open.

## Browser SQL access verified — 2026-09-05

Denys explicitly authorized use of the second Chrome profile. The existing Railway session
opened the exact HoReCa project and staging environment. Two catalog-only SELECT queries ran
successfully in PostgreSQL's Database > Data SQL editor over the browser connection, without
local SSH or changing networks. This removes SSH connectivity as a prerequisite for this inventory.

Observed results:
- Current database: `railway`; current user: `postgres`; current schema: `public`.
- Non-template databases: `postgres` and `railway`, both owned by `postgres`.
- In `railway`, the only non-system schema returned was `public`, owned by `pg_database_owner`.
- No non-system tables were returned in `railway`; no application migration table is present.
- The only role outside the `pg_` prefix was `postgres`, with login, superuser, createdb,
  createrole and bypassrls enabled. The two proposed application role names do not yet exist.

Both SELECTs passed (1 and 4 result rows respectively); no database mutation occurred. No
credentials were inspected, public database proxy enabled, or deployment triggered. Application
services remain offline. Next, review the exact role/grant preparation for database `railway`
and the existing migration-runner execution plan before separately approved provider changes.
Browser SQL is now a verified administration route; the application itself uses Railway's
internal database connection. Budget, sender and other Stage 2 gates remain unresolved.

## Exact first DB preparation step — review only, 2026-09-05

Additional browser catalog SELECT passed: 7 result rows, all inspected across both pages.
Server is PostgreSQL `16.15`; database ACL is NULL (default privileges); public schema ACL is
`{pg_database_owner=UC/pg_database_owner,=U/pg_database_owner}`. Non-system relations and
functions: zero. Explicit default-privilege entries: zero. Memberships for roles outside the
`pg_` prefix: zero. No existing PUBLIC schema CREATE grant needs revocation.

The next proposed action targets only the existing staging PostgreSQL service and database
`railway`. This single DO statement is atomic: a failed guard or assertion rolls back its role
and grant changes. It intentionally fails on an existing role rather than modifying it or
silently treating an uncertain earlier execution as success. Recheck target IDs in the browser
before execution. This statement has been reviewed, not run; explicit DB-change approval remains
required. It creates no password, login capability, application table, deployment or paid resource.

```sql
DO $prepare_roles$
BEGIN
  IF current_database() <> 'railway' OR current_user <> 'postgres'
     OR current_setting('server_version_num')::integer / 10000 <> 16 THEN
    RAISE EXCEPTION 'Unexpected database, administrator or PostgreSQL major version';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname IN ('horeca_staging_migrator', 'horeca_staging_runtime')
  ) OR EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
  ) OR EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
  ) OR EXISTS (SELECT 1 FROM pg_default_acl) THEN
    RAISE EXCEPTION 'Inventory changed; repeat read-only review';
  END IF;

  CREATE ROLE horeca_staging_migrator NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  CREATE ROLE horeca_staging_runtime NOLOGIN NOINHERIT NOSUPERUSER
    NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  GRANT CONNECT ON DATABASE railway TO horeca_staging_migrator, horeca_staging_runtime;
  GRANT USAGE ON SCHEMA public TO horeca_staging_migrator, horeca_staging_runtime;
  GRANT CREATE ON SCHEMA public TO horeca_staging_migrator;

  IF NOT has_schema_privilege('horeca_staging_migrator', 'public', 'CREATE')
     OR has_schema_privilege('horeca_staging_runtime', 'public', 'CREATE')
     OR has_database_privilege('horeca_staging_runtime', 'railway', 'CREATE') THEN
    RAISE EXCEPTION 'Unexpected effective CREATE privileges';
  END IF;
END
$prepare_roles$;
```

Fresh review pass: role creation and grants share one atomic statement; existing identities,
owners, schema ACL entries and role memberships are not rewritten. Runtime cannot inherit the
migrator identity. Existing PUBLIC database CONNECT/TEMP permissions remain; NOLOGIN prevents
both new roles from authenticating at this step. This does not yet establish runtime data grants
or actual login/DDL-denial integration evidence.

After an approved successful run, use SELECT to verify exactly two roles, all privileged flags
false, no memberships, CONNECT/USAGE true for both, schema CREATE true only for migrator and
database CREATE false for both. If response is ambiguous, inspect these catalogs before retrying.
Do not run migration until separate LOGIN/secret provisioning, runner configuration and migration
approval are complete. The accepted target command remains `python -m alembic upgrade head`,
expected head `0018_job_runtime`, one controlled run with restart policy NEVER.

This addition belongs to the existing `docs(deploy): complete CRA-122 preparation boundaries`
checkpoint; focused verification is catalog evidence, fresh SQL review and `git diff --check`.
No local commit or Git index update is implied.

## Approved SSH registration — 2026-09-05 11:39 UTC

Denys approved registration of the existing public key after the explicit access-change request.
The personal Railway account now lists `horeca-staging-diagnostics`, RSA 4096, fingerprint
`SHA256:XGV1T+1jdXJi5AZ+bT6x4HhJRf3ums6STtMosqUctig`. Registration and subsequent list verification
succeeded. Only the public key was transmitted; no private key or database credential was read.
This is an account SSH key, not a database role or a staging-only credential.

The intended metadata-only SELECT did not execute: the system SSH client timed out connecting
to `ssh.railway.com:22`. DNS returned an IPv4 address; an explicit IPv4 retry with a 10-second
connect timeout and strict host-key checking also timed out before authentication. Railway API
access worked. The cause of the TCP failure (local network, upstream route or Railway endpoint)
is not established. No server host-key warning was bypassed and no network settings changed.

The later browser SQL check above supersedes restoring SSH as the next inventory step.
No further key registration is needed. No public database proxy, SQL mutation, migration,
application deployment or email send occurred. Budget, sender and remaining Stage 2 decisions
are still open. Revocation, if requested later, must target the registered key above.

## Live read-only preflight — 2026-09-05 11:30 UTC

Target project/environment IDs match the existing staging plan. The installed Railway CLI
authenticated successfully outside the network-restricted sandbox. The local directory has
no Railway project link; explicit-ID GraphQL queries avoided creating one.

Observed directly today:
- Exactly one environment: staging.
- All nine application services have null source, no latest deployment and hasEverDeployed=false.
- Environment deployment triggers: zero.
- All nine use RAILPACK; Dockerfile/root/health paths remain unset.
- Migration and cron still use ON_FAILURE with 10 retries; reviewed target remains NEVER.
- Existing worker/migration/cron commands and all five UTC schedules match the plan.
- Serverless is disabled on all application services.
- PostgreSQL latest deployment is SUCCESS at the previously recorded deployment ID. This is
  provider deployment state, not a successful SQL connectivity or schema check.
- Existing learning-assets bucket has zero objects and zero bytes.

A private SSH attempt to run only SELECT database names did not execute SQL: Railway reported
no registered SSH keys. The existing local public key id_rsa.pub was located without reading
private-key material. Registration was requested from Denys and has not occurred. Do not use
a public DB proxy or reveal credentials as a workaround. DB roles, grants and migration head
remain unverified. Bucket CORS/URL style/credential granularity were not exposed by the queried
metadata fields and remain unverified.

Executed result: source/settings inventory and bucket-count queries passed; SQL inventory
blocked before execution. No variables, credentials, resources, schedules, deployments or
database objects changed. No application tests were rerun for this read-only provider pass.

## Stage 2 completion checklist — 2026-09-05

Status: reviewed planning proposal, not executed SQL or provider configuration. Denys authorized
the audit follow-up sequence. Budget and sender were requested and remain unresolved.

### Database preparation and evidence

Keep the existing database and schema layout. Proposed new login roles are
`horeca_staging_migrator` and `horeca_staging_runtime`; names must first be checked for collisions.
Do not reuse existing names with unknown owners or change existing memberships automatically.

Before preparing the final executable SQL, use an approved private diagnostic connection to
collect only: database name/owner, schema owners/ACLs, application table/sequence/function owners,
role flags and memberships, default privileges, and presence/version of `alembic_version`.
Do not read customer rows, password hashes, connection strings or role passwords. The live
inventory is recorded in the browser SQL sections above; emptiness was verified from catalogs,
not inferred from offline services.

For the confirmed empty staging application schema, the proposed administration sequence is:

1. Create both roles with NOLOGIN initially, NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
   NOREPLICATION and NOBYPASSRLS. Keep runtime outside migrator/owner/admin memberships.
2. Grant CONNECT to the exact existing database and USAGE on the existing `public` schema.
   Grant CREATE on that schema to migrator only. Verify effective runtime CREATE is false,
   including PUBLIC/inherited grants. Any required revocation needs the exact observed ACL diff.
3. Enable LOGIN and provision separate random passwords only through the approved secret channel.
   Assign the migration URL only to migration-runner and runtime URL only to API/worker/cron.
4. Run the separately approved migration as migrator, so application objects are owned by it.
   Do not apply generic ownership changes to existing objects if inventory was nonempty.
5. After migration, grant SELECT/INSERT/UPDATE/DELETE on the explicit application-table inventory
   to runtime, excluding `alembic_version`. Grant USAGE on only sequences actually required.
   No TRUNCATE, REFERENCES, TRIGGER, schema CREATE, ownership or grant option.
6. Verify function/trigger requirements from the resulting inventory. Runtime must not own or
   disable the append-only triggers. Do not blindly revoke function execution without evaluating
   the trigger dependencies. Future migrations require a reviewed grant reconciliation.
7. Prove role flags, memberships and effective object permissions with PostgreSQL privilege
   functions before runtime deployment. Exercise actual synthetic allowed/denied paths during
   the separately approved staging acceptance; catalog assertions alone are not an integration pass.

Illustrative grant shape only, with identifiers intentionally unresolved:

```sql
GRANT CONNECT ON DATABASE "<verified_database>" TO horeca_staging_migrator, horeca_staging_runtime;
GRANT USAGE ON SCHEMA public TO horeca_staging_migrator, horeca_staging_runtime;
GRANT CREATE ON SCHEMA public TO horeca_staging_migrator;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."<reviewed_application_table>"
  TO horeca_staging_runtime;
GRANT USAGE ON SEQUENCE public."<reviewed_required_sequence>" TO horeca_staging_runtime;
```

This is not an apply script. Avoid broad grants on every table, which would include migration
metadata. Default privileges are owned by the object-creating role and affect future objects
only; they do not repair existing grants. This proposal uses explicit post-migration grants
until a complete future-object policy is reviewed. Sources:
[PostgreSQL 16 GRANT](https://www.postgresql.org/docs/16/sql-grant.html) and
[default privileges](https://www.postgresql.org/docs/16/sql-alterdefaultprivileges.html).

### Storage wiring and browser acceptance

Only API receives bucket credentials. Proposed references for existing `learning-assets` are:

| Application variable | Provider reference |
| --- | --- |
| `STORAGE_BUCKET` | `${{learning-assets.BUCKET}}` |
| `STORAGE_ENDPOINT_URL` | `${{learning-assets.ENDPOINT}}` |
| `STORAGE_REGION` | `${{learning-assets.REGION}}` |
| `STORAGE_ACCESS_KEY_ID` | `${{learning-assets.ACCESS_KEY_ID}}` |
| `STORAGE_SECRET_ACCESS_KEY` | `${{learning-assets.SECRET_ACCESS_KEY}}` |

Verify the resource/environment IDs and reference resolution without displaying values.
The S3 bucket name is the provider BUCKET value, not its display name. Verify the provider's
required URL style before execution; the current Boto3 factory has no explicit addressing-style
override. Credentials remain provider-owned and absent from frontend build variables.

The code uses `generate_presigned_post`, browser FormData POST, server `head_object`, and
presigned GET. Review bucket CORS for the exact staging browser origin and these operations.
After a separate configuration/data approval, prove an authorized synthetic image upload,
metadata/size/type confirmation and protected download from the real browser origin; also
prove anonymous access denial and expired-signature rejection. Do not replace POST with PUT
inside this planning issue if a provider compatibility issue appears.

Railway private buckets are authenticated object storage; they are not private-network-only
services. Preserve HTTPS and signed access, and account for service egress. Verify available
credential permission granularity rather than claiming an unobserved custom IAM policy.
References: [bucket variables and access](https://docs.railway.com/storage-buckets),
[bucket networking/billing](https://docs.railway.com/storage-buckets/billing).
This is configuration/test preparation, not a live bucket or CORS verification.

### Exact remaining handoff inputs

| Input | Owner / evidence |
| --- | --- |
| Monthly staging budget and hard-limit consequence | Denys; no numeric assumption |
| Resend sender domain/address and permitted test recipients | Denys; no unrelated domain reuse |
| Candidate acceptance | Denys; published source `5a1e650924944ef1f7d444647ea90d5319400ce1` |
| DB inventory and executable role/grant diff | Technical executor through approved private access |
| Storage URL style, reference names and CORS delta | Technical executor; metadata only |
| Final CPU/memory caps and provider secret operations | Reviewed after budget/provider inventory |
| Source/settings apply, migration, rollout and test sends | Separate execution approvals |

### Documentation checkpoint map for this follow-up

1. `docs(project): reconcile published CRA-123 checkpoint`: README, STATUS, CONTEXT,
   `.harness/GIT-WORKFLOW.md`, `.harness/TESTING.md`, testing index and CRA-123 evidence.
2. `docs(deploy): complete CRA-122 preparation boundaries`: this existing plan, including the
   preserved earlier uncommitted preflight additions, and its canonical Linear counterpart.

Verify local links, exact diff, stale current-state statements, absence of secret values and
the selective file inventory. No application code changes; documentation-only TDD exception.
The index remains unchanged until explicit local-commit authorization. No push is implied.

## Latest Stage 2 read-only checkpoint — 2026-09-04 20:07 UTC

This checkpoint supersedes the earlier publication and provider-observation statements below.
Denys authorized and completed publication of four commits through
`5a1e650924944ef1f7d444647ea90d5319400ce1`; remote `main` was verified at that exact SHA.
It includes CRA-123 `ec27d19e023dc48f7a66103967c5d23f23281bfe`. Proposed all-role deployment
candidate is the published `5a1e650` source, subject to exact Stage 2 acceptance; no source is bound.

Read-only Railway CLI, targeted GraphQL queries and the authenticated browser confirm:

- Exactly the known `staging` environment exists; project/workspace IDs match the earlier record.
- PostgreSQL is Online with the same successful deployment `46bb859f-58c8-4318-aa5a-1aacbf62d522`.
- All nine application services have null source, null latest deployment and `hasEverDeployed=false`.
- There are zero project deployment triggers. This does not prove future binding cannot add one.
- Application root directories, Dockerfile paths and health paths are unset; builder is RAILPACK.
- Existing worker/migration/cron start commands match the matrix below; API/web commands are unset.
- Five cron schedules match the matrix. Every application role currently uses ON_FAILURE with
  10 retries. Migration and cron need an explicitly approved change to NEVER before execution.
- Variable-name-only inventory contains 12 PostgreSQL variables and no application variables.
  No variable values were requested. This does not establish DB grants or usable secret references.
- The browser shows `learning-assets` empty and API without public networking. The known web
  origin remains the only public application origin reported by the status command.
- The API settings page shows one replica and maximum limits of 8 vCPU / 8 GB. These are ceilings,
  not a measured cost estimate or approved budget. Hobby is confirmed; spending cap is unresolved.
- An initial UI warning called `europe-west4-drams3a` invalid while region options loaded. It
  disappeared, and the live regions query includes that exact Amsterdam region. Do not change
  regions based on the transient warning. Legacy `ServiceInstance.region=null` is not placement proof.

GitHub access prerequisite resolved on 2026-09-04 after explicit Denys approval. Existing Railway
App installation `136040665` now includes only the additional `GarnikSacsha/HorecaFam-` repository,
preserving the previous ten selected repositories (eleven total). Save completed, and the Railway
source picker subsequently returned the exact target repository. The picker was closed without
selecting it. No Railway source binding, provider setting or deployment was initiated by this action.
This approved GitHub access change is separate from the earlier read-only provider checkpoint.

### Revised configuration procedure for review

1. Completed: inspect the existing installation and, with explicit approval, add only
   `GarnikSacsha/HorecaFam-`, preserving the previous ten selected repositories. Verify the exact
   repository is visible in Railway without selecting or binding it.
2. Resolve the exact SHA selection/evidence mechanism and obtain Stage 2 acceptance. A mutable
   `main` selection alone is not proof. Recheck SHA before each independently authorized rollout.
3. Under separate provider-settings approval, suspend the five cron schedules, preserve their
   restoration map, set migration/cron restart policy NEVER, configure Dockerfile roots and
   health/start settings from the matrix, and disable source push triggers. Review every diff.
4. Railway's documented UI uses Alt+Deploy to commit staged changes without redeployment.
   The live API schema exposes `environmentPatchCommitStaged(environmentId, skipDeploys: true)`
   with the same skip-deploy purpose. Use only after reviewing the exact staged set and separate
   approval. Never call its default behavior or a generic Deploy during configuration.
5. Verify no deployment was created, no source trigger remains enabled, all roles remain offline,
   and schedules remain suspended. `skipDeploys` is not a promise that cron schedules are disabled.
6. Resolve DB identities, scoped secret references, Resend sender/recipients and budget before
   migration/runtime gates. Restore each reviewed cron schedule only after its rollout approval.

Networking settings are applied immediately according to Railway docs, not staged. Preserve all
existing networking and database/bucket resources. No `.railway/railway.ts` apply is appropriate.

This follow-up edits only this planning document and its canonical Linear record. Intended next
documentation checkpoint: `docs(deploy): record verified Stage 2 provider preflight`; validation is
source/target cross-check, local links, exact diff and absence of secret values. No new commit or
push is authorized by the prior completed three-commit map. No code tests were rerun because no
application code changed; these are provider-read observations, not staging acceptance tests.

References: [staged changes](https://docs.railway.com/deployments/staged-changes),
[GitHub autodeploy controls](https://docs.railway.com/deployments/github-autodeploys).

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
It is published within `5a1e650` and is not bound to staging. The baseline above describes
the historical CRA-119 source; the current proposed all-role source is `5a1e650`.

CRA-123 is corrected, locally verified and published; deployment-candidate acceptance remains open. See
[the exact evidence](../testing/caddy-delivery-cra-123.md). The Caddy findings require an accepted
corrective disposition before rollout. If application files
change, the old baseline is no longer the deployment candidate: record a separately accepted,
committed and published replacement SHA here and in CRA-122 before provider execution. Do not
silently deploy a branch's newer tip or mix application SHAs across services.

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


</details>
