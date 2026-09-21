# CRA-122 source/build preparation — 2026-09-07

## Current routing — 2026-09-16

Use [STATUS](../../STATUS.md) and [the reconciliation ledger](../testing/reconciliation-2026-09-16.md) before the dated records below.
The leading STATUS checkpoint is the single current delivery/content/acceptance summary.
The reconciliation ledger below predates subsequent CRA-237/238 delivery and Training publication.
Do not repeat accounts, activation, imports, publication, CORS or migrations from dated records.
Consult the current checkpoint before choosing a source packet or executing a next operation.

The older source/build JSON files are historical preparation inputs, not the current delivery
manifest: source binding was not applied, the build settings were applied in their recorded
September 7 boundary, and scoped CORS was applied in its September 13 boundary. Do not reapply
or retarget these files from this documentation. Resolve each service source from STATUS and
its delivery report; the dirty checkout is not an immutable release candidate.

Dated observations, test counts and original runbook requirements below retain their original
scope. They do not establish fresh provider state or override this current routing.

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

## Web rollout proposal — 2026-09-11

Preparation only; no web upload or deployment has run. Use the existing isolated source export
for commit `0956e7bb1af8914b94bc064e65e6cfaf4f88a775`, already used for migration/API delivery.
All 377 files match the existing manifest, with zero additional files or hash mismatches.
The source ZIP SHA-256 recorded in that manifest is
`5049a598a44316e1349d74535cc6674de011c7f83b82cc9fcc93376a66c587b6`.

Fresh web settings: staging; EU West Amsterdam; one replica; `/frontend` root; Dockerfile builder
with `Dockerfile` path; no start override or pre-deploy step; `/healthz`; port 8080; restart
On Failure / 3. Existing ceilings remain 8 vCPU / 8 GB, not measured usage or a monetary cap.
Boolean-only variable checks confirm PORT, API_UPSTREAM and public domain match the reviewed
8080 / private API:8000 / web-staging-4268.up.railway.app targets. No setting was changed.
The API private-console read-only database probe passed; the public web service is still offline.

After explicit web upload/deployment approval, run from the existing isolated export directory
`outputs/staging-candidate-0956e7b-preflight/source`, never the dirty repository root:

```powershell
rtk railway up . --path-as-root --project 04320f63-ab40-426f-ab35-02fcb365c3b8 --environment d8e64109-9863-4faa-a45e-f072adb3cfac --service 167269a6-26cb-40f6-b129-b698127c87ee --detach --message "CRA-122 web candidate 0956e7bb1af8914b94bc064e65e6cfaf4f88a775"
```

This uploads and deploys web; it is not an upload-only command. Capture deployment ID, actual
Docker build and successful health. Verify HTTPS `/healthz`, public entry/login SPA routes,
same-origin `/api/v1/health`, unsupported API/missing asset 404 behavior and security/cache
headers before reporting website delivery. Stop on failure; do not redeploy API, rerun migrations,
enable cron, send email or provision accounts as part of this operation. No prior web deployment
exists for rollback; failure containment and corrective changes require their reviewed boundaries.

Local preparation checks: five delivery/topology tests passed, zero failed/skipped; initial
sandbox attempt had two test-file spawn EPERM failures before assertions and the permitted retry
passed. Full browser suites and Docker builds were not rerun in this preparation.

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

## Delivery decision addendum — 2026-09-08

The [unified acceptance packet](staging-acceptance-cra-122.md) proposes
`fafec73ad7f3438e1b545acea7cde3018b7f2fbf` and migration 0019; selection is still pending.
The existing JSON drafts retain the earlier accepted candidate.

Read-only checks in this preparation:
`railway service source connect --help` exposes repo/image, branch and target selectors,
but no suppression flag. Official [service CLI documentation](https://docs.railway.com/cli/service)
likewise does not establish an atomic bind-with-autodeploy-disabled operation.
[GitHub autodeploy documentation](https://docs.railway.com/deployments/github-autodeploys)
describes disabling autodeploy after a repository is connected.
[Staged changes](https://docs.railway.com/deployments/staged-changes) document applying settings
without an immediate redeploy; this does not establish suppression of future GitHub events.
Conclusion: the required binding guarantee remains unproven. Do not connect then disable.

Option 1 retains GitHub delivery: obtain an explicit supported sequence/guarantee from Railway,
review its precise effects on all nine services, then request authorization for that operation.
The existing support question is prepared but has not been sent.

Option 2, proposed if that guarantee is unavailable: explicitly approve manual delivery from
an isolated export of the selected Git tree, retaining source-less services and null schedules.
Prepare an archive manifest and hash, verify the export contains no workspace-only files or
secrets, and review the root/Dockerfile mapping for each of the nine existing services.
Do not upload the dirty working directory. Reconcile ignore rules with the exported manifest.
Use explicit existing project/environment/service targets; never implicit project creation.
The official [up command](https://docs.railway.com/cli/up) uploads **and deploys**, even in
detached mode. Each invocation therefore belongs to its migration/runtime/cron rollout gate,
not a harmless source-preparation step. No upload command has been executed.
Confirm cron-role upload/start behavior before using this alternative: a disabled schedule
alone must not be assumed to prevent the initial command from running.

Option 2 is a workflow proposal, not an approved substitute or a proven nine-service rollout.
Neither option resolves secrets, initial operator creation, resource sizing or live acceptance.
No provider-state refresh or mutation was performed during this documentation preparation.

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

Build/start package applied after Denys's confirmation; source binding remains a draft.
Denys accepted source candidate
`2275cee1ae46da708f33a032229e708c73a966c8`; this does not authorize source binding or deployment.
Project `04320f63-ab40-426f-ab35-02fcb365c3b8`, environment
`d8e64109-9863-4faa-a45e-f072adb3cfac`. Exact service IDs are in both payloads.

## Build/start execution result

Patch `fea986f8-c963-41f7-9b13-49053be89380` is COMMITTED at
`2026-09-07T19:40:13.612Z`, applied once with skipDeploys=true. Preflight confirmed an empty
pending inventory, unchanged reviewed draft, exact remote SHA and nine undeployed services
without repository or push triggers. Railway omitted unchanged fields from the staged patch;
literal equality stopped before apply, then an exact comparison against the live baseline
proved the normalized 39-field delta matched the approved outcome. No additional change.

Postflight: 84 of 93 desired fields match ServiceInstance. Its nine builder fields still report
RAILPACK, but saved environment config explicitly contains DOCKERFILE and Dockerfile path for
all nine services. Nine saved-config builder checks plus 84 instance checks support the settings
result. These representations differ; do not claim ServiceInstance itself reports DOCKERFILE.
Default ON_FAILURE and sleep=false are absent from saved config and confirmed in ServiceInstance.
Actual Dockerfile use is a later build check, not proven by configuration.

All nine repo fields are null, hasEverDeployed is false and active-deployment count is zero.
The source object is now present because it contains rootDirectory; object presence alone
does not mean a repository is connected. The environment trigger query returns zero rows and
no next page. Five cron schedules remain null. No source binding, build, migration, secret/DB
operation or send occurred. The JSON is retained unchanged as the exact reviewed input.
The preparation-only claims below describe the earlier planning checkpoint.

## Fresh evidence

### Supported connection workflow investigation — 2026-09-08

Read-only investigation completed; no provider mutation was attempted in this follow-up.
The installed official CLI explicitly states that GitHub source connections create deployment
triggers for matching project environments. Live ServiceConnectInput exposes only repo, branch
and image; it has no autodeploy suppression flag. ServiceInstanceAutoDeployUpdateInput is a
separate operation with projectId, environmentId, serviceId and enabled. Its schema does not
promise that a disabled state set before a repository exists survives source connection.

The official [GitHub autodeploy documentation](https://docs.railway.com/deployments/github-autodeploys)
describes linked-branch push deployment and a separate Disable action. The
[CLI source documentation](https://docs.railway.com/cli/service) documents connection options,
but no atomic connect-with-autodeploy-disabled option. These sources do not prove that such a
mechanism is impossible; they leave its supported contract unresolved. Serial GraphQL mutations
would not establish transactional isolation or remove the intermediate trigger window.

The exact-SHA source draft remains unapplied. skipDeploys addresses application of staged
settings; it is not evidence that future GitHub events are suppressed. Neither branch=null nor
the successful side-effect-free preview closes that separate gate. No repeated preview is needed.

Next bounded step: obtain Railway's supported API sequence or documented guarantee below,
then revise the source-only payload and its preflight/postflight before requesting execution.
Do not send this question externally without Denys's explicit message authorization.

## Railway support request sent — 2026-09-08

Denys explicitly authorized sending the prepared technical question. It was submitted once
through Railway Central Station as a public Technical Help thread, with service N/A for
the general API/workflow question. No credentials, repository URL, project/service IDs or
attachments were included.

[Connect pinned GitHub source without initial deploy or push autodeploy](https://station.railway.com/questions/connect-pinned-github-source-without-ini-0e7a6cfe)

Post-submit UI readback verified the title, full question, author and status
**Awaiting Railway Response**, with 0 replies at verification. Earlier unsent wording is historical.
Sending this request does not resolve the source-binding guarantee or authorize provider changes.
Next: assess the supported sequence in the response before preparing any source mutation.
No automatic follow-up monitor was configured.

**Prepared Railway support question (sent; exact text retained):**

> We have existing, never-deployed services with no GitHub source or deployment triggers.
> We need to connect a GitHub repository at a pinned full commit SHA while guaranteeing both
> zero initial deployments and disabled future push autodeploy from the instant of connection.
> The services include a migration runner, so connecting and disabling afterward is unsuitable.
> Does setting serviceInstanceAutoDeployUpdate(enabled:false) before a source exists persist
> through source binding, including when status currently reports NO_REPO? If so, which source
> mutation preserves that flag? Alternatively, is there an atomic source-binding API or staged
> config field that disables trigger creation? Please give the supported sequence and readback
> fields proving the effective state. Does environmentPatchCommitStaged(skipDeploys:true) only
> suppress the immediate deploy, or also affect push-trigger creation? What does branch:null
> mean when repo and commitSha are supplied?

If Railway cannot provide this guarantee, an archive upload of the accepted Git tree is an
alternative to investigate and propose separately. It changes the approved GitHub binding
workflow and initiates builds/deployment; no archive upload or rollout is authorized here.

Documentation boundary: this file only; intended future checkpoint
`docs: record CRA-122 source binding contract gap`. Verification: official CLI/schema readback,
focused document inspection and git diff --check. No code/API/data contract change, commit,
push, Linear update, build, migration or deployment belongs to this investigation.

### Source preflight continuation — 2026-09-08

Denys subsequently approved the exact metadata transmission. The authorized
environmentPreviewChangeSet completed successfully: diagnostics=[], nine resource.update
effects, each limited to its service source, severity=safe and deployEffect=deploy.
The submitted intent already contained severity=safe and deployEffect=deploy, so the returned
effects are not independent proof of initial deployment behavior or future push suppression.
No statement about atomic autodeploy suppression was returned. Preview success therefore
does not close the source-binding gate. No source mutation or apply was attempted.

Live schema exposes serviceInstanceAutoDeployStatus and serviceInstanceAutoDeployUpdate
with explicit project/environment/service IDs and enabled boolean. Read-only status checks
for all nine targets returned enabled=false, canEnable=false, reason=NO_REPO. This proves
only the current source-less state, not suppression after binding. No update was called.

The live schema describes environmentPreviewChangeSet as an experimental preview without
side effects. Its RailwayChangeSet format was checked in the official CLI source:
src/iac/change_set.rs, compiler.rs and engine.rs. Prepared a nine-entry resource.update
preview, each limited to source on the existing named service, preserving its rootDirectory,
adding repository GarnikSacsha/HorecaFam-, branch null and the accepted full SHA.
The intended response contains diagnostics/effects only. This preview does not stage, bind
or deploy and is not evidence that branch null suppresses future push triggers.

Automatic approval review rejected the attempted preview before execution, requiring explicit
authorization for transmitting repository/SHA and target identifiers to Railway. No retry or
alternate transmission was attempted. Exact approval scope: send the nine-service source-only
preview for this one repository to the existing authenticated Railway public GraphQL API in
project 04320f63-ab40-426f-ab35-02fcb365c3b8 / environment
d8e64109-9863-4faa-a45e-f072adb3cfac; return diagnostics/effects. No secrets or customer data.
No environmentApplyChangeSet, environmentStageChanges, serviceConnect or deployment call.
Next: run this exact preview after approval and assess its evidence before any binding proposal.

Direct GitHub main readback matches the accepted SHA. All nine application services report
source null, builder RAILPACK, unset root/Dockerfile/build override/health/pre-deploy command,
ON_FAILURE with 10 retries, sleepApplication false and hasEverDeployed false. All schedules
are null. Seven worker/migration/cron start commands already match the table below; API and
web overrides are null. Nine trigger queries each returned zero rows and no next page.
The single-region and replica fields are null: they do not prove Amsterdam/one replica.
This package does not change placement, replica limits, networking, variables or resources.

## Reviewable payloads and order

1. [Build/start settings draft](cra-122-build-settings.draft.json): nine service entries,
   Dockerfile builder and path, correct build roots, role commands, health and restart policy.
   It contains no repository connection. A rootDirectory inside `source` is build context only.
2. [Source binding draft](cra-122-source-binding.draft.json): nine repository connections to
   `GarnikSacsha/HorecaFam-`, exact accepted commitSha, branch null. This is a schema-checked
   proposal; null branch is **not yet proven** to prevent trigger creation during binding.

| Role | Root | Start command | Health | Restart |
| --- | --- | --- | --- | --- |
| api | /backend | python -m app.api_server | /api/v1/health | ON_FAILURE, 3 |
| worker | /backend | python -m app.worker | unset | ON_FAILURE, 3 |
| migration-runner | /backend | python -m alembic upgrade head | unset | NEVER |
| web | /frontend | Docker CMD (Caddy) | /healthz | ON_FAILURE, 3 |
| cron-stale-jobs | /backend | python -m app.cron stale-jobs | unset | NEVER |
| cron-attempt-expiry | /backend | python -m app.cron attempt-expiry | unset | NEVER |
| cron-retake-deadlines | /backend | python -m app.cron retake-deadlines | unset | NEVER |
| cron-security-cleanup | /backend | python -m app.cron security-cleanup | unset | NEVER |
| cron-audit-retention | /backend | python -m app.cron audit-retention | unset | NEVER |

All roles retain cronSchedule null, preDeployCommand null and sleepApplication false.
Build-command override is null. Migration is only its runner command, never an automatic
pre-deploy hook. NEVER roles omit maxRetries because it is inapplicable; the old stored 10
may remain but does not change NEVER semantics. Web inherits the existing Docker CMD.

## Execution boundary after separate approval

For each draft, recheck exact target IDs, accepted remote SHA, zero deployments/triggers and
five disabled schedules. Inspect pending patch structure with decryptVariables false; require
an empty inventory before adding this draft. Unexpected changes stop application, never
discard them automatically. Submit only the approved draft through environmentStageChanges
with merge true, inspect the complete staged diff, then separately approved application uses
environmentPatchCommitStaged with skipDeploys true. Verify COMMITTED and appliedAt, and read
back all mapped fields and hasEverDeployed false for all nine roles. Never use railway up,
Deploy Latest Commit, or the unrelated .railway/railway.ts configuration.

The build draft can be reviewed independently while the source-trigger question is resolved.
For the source draft, do not commit until the provider's supported mechanism demonstrably
keeps push autodeploy disabled at binding time. The public schema exposes branch/commitSha,
but no explicit autodeploy boolean in EnvironmentConfig. Official documentation describes
a separate Disable control. Do not infer that checkSuites false, branch null, watch patterns
or skipDeploys disable future pushes; do not rely on deleting a trigger after it becomes live.
If staging exposes an extra trigger or branch requirement, stop and revise the exact proposal.

After source application, require nine exact repository/SHA entries in committed configuration,
zero triggers and zero deployments. ServiceSource query exposes repo/image only, so it cannot
alone prove commitSha. Later deployment approval still requires explicit commitSha and each
deployment's immutable evidence. The first binding operation has not been exercised here.

## Rollback and remaining gates

Before commit, discard only the exact newly reviewed staged entries after an explicit decision.
After commit, prepare a corrective settings patch from the recorded preflight; never replay
the entire prior environment configuration. Keep cron suspended and preserve both applied
variables, the sealed Resend key, DB, volume and bucket. No automatic restore, source deletion
or resource deletion is authorized by this draft.

Before any rollout: prove placement/replicas and cost controls, finish scoped secrets/DB grants,
initial operator procedure and product-scope disposition. Build configuration is not live
acceptance. Current 809-test evidence is unchanged; no build or application suite ran here.

Documentation commit map, not commit authorization: one coherent preparation checkpoint with
this file, the two JSON drafts and navigation in staging-cra-122.md. Verify payload/schema
constraints, accepted Git blob paths/commands, service inventory, links, and exact diff. Leave
the index untouched. No production code or API/schema contract changes.

Sources: [live config schema](https://backboard.railway.com/schema/environment.schema.json),
[GitHub autodeploy controls](https://docs.railway.com/deployments/github-autodeploys),
[staged changes](https://docs.railway.com/deployments/staged-changes),
[canonical execution plan](staging-cra-122.md).

Validation: two payloads with nine matching service IDs each passed the schema constraints
used here (structure, types, anyOf, required, enum and const); this was a focused check, not
a full JSON Schema implementation. No dependency was added. Nine Dockerfile lookups against
the accepted Git SHA passed, three relative links exist, and git diff --check passed.
The Git index remains empty. No provider validation/apply, Docker build or application tests
were run by this preparation.
