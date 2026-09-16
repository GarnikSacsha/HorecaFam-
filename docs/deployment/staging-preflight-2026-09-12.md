# CRA-122 — staging preflight and first learning journey — 2026-09-12

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

Denys requested all preparation that can be completed without his participation. This records
fresh read-only provider/database evidence and local verification. It does not authorize a
deployment, email send, credential change, content publication, or Git action.

## Authorized execution checkpoint — 2026-09-13

This checkpoint supersedes the preparation-only provider state below. Denys changed the
existing HoReCa Resend key to Sending access and explicitly authorized the prepared staging
worker deployment, existing invitation delivery attempt and scoped bucket CORS operation.
Sending access was confirmed in the provider UI; no replacement key was created.

The immutable 377-file export and ZIP were reverified before deploying only the worker from
`0956e7bb1af8914b94bc064e65e6cfaf4f88a775`. Railway deployment
`aad4336b-ebdf-413b-a1e3-4a4bf46dfc76` reached SUCCESS; worker is Online. Image digest:
`sha256:7549e2bcca02fd15d4ef7bc663cc60ad13e8f4d43e5c6303a616d7cf24a5ca25`.
API/web, migrations and the five offline crons were not redeployed or started.

Applied the exact [CORS proposal](staging-cors-proposal.json) after confirming an empty rule
set. PutBucketCors returned 200. Readback matches the intended fields; the provider adds an
empty rule ID. Real presigned-target OPTIONS checks: staging origin returned 200 with POST
and Content-Type allowed; an unrelated origin returned 403 without origin permission.
No asset was uploaded. These two checks passed; actual browser upload remains unverified.

The worker claimed the existing invitation job, but Resend returned HTTP 403: the `resend.dev`
testing domain can send only to the account owner's address. The configured sender is
`onboarding@resend.dev`; the existing recipient is outside that testing allowance. No accepted
send was observed. The latest inspected runtime logs show two failed attempts with ResendError
and another automatic retry scheduled under the existing bounded policy. No manual retry,
recipient substitution, duplicate invitation or retry-policy change was performed. The pending
EmailDelivery provider value `fake` is an enqueue default, not evidence of a fake transport.

The Resend Domains screen has no verified sending domain. Owner input is now required to
choose a sending domain and complete its verification, or explicitly choose the account-owner
test-recipient route. Do not reuse the failed domain belonging to another project implicitly.
After provider acceptance, complete invitation/login and the Admin/Employee content journey.
Live Employee acceptance and menu publication are still open; CRA-122 is not complete.

Only this report and navigation checkpoints in STATUS and the acceptance runbook changed in
this execution step. No application edits, Git index changes, commits or pushes. Existing
local test results below still apply to the same source; they were not rerun for provider-only
operations. The diagnostic API console was disconnected after inspection.

## Scope and checkpoint boundary

One documentation checkpoint: `docs: record staging preflight and first learning journey`.
Expected paths: this report, `staging-cors-proposal.json`, and only the September 12 navigation
hunks in `../../STATUS.md` and `staging-acceptance-cra-122.md`. Checks: JSON parse, relative links,
diff hygiene and unchanged application/index inventory. No commit is performed. The local
content report and walkthrough under `outputs/demo-content-full/` stay outside Git.

## Fresh state supersedes the September 11 account snapshot

The main worktree is at `0956e7bb1af8914b94bc064e65e6cfaf4f88a775`. Its existing isolated export
contains exactly 377 manifest files: zero hash mismatches, zero extra files; source ZIP hash
matches the recorded manifest. The dirty repository is not a deployable export.

Railway CLI and the existing provider UI agree: API, web and PostgreSQL are online;
migration-runner is completed; worker and all five cron services are offline. No service was
started, stopped or reconfigured. Public HTTP checks earlier in this session passed 7/7.

Read-only transactions in the running API console used the deployed Settings, required
`APP_ENV=staging`, `SET TRANSACTION READ ONLY`, and a five-second statement timeout. Only counts
and lifecycle enums were printed; no identities, addresses, tokens, payloads or credentials.

| Application state | Fresh result |
| --- | --- |
| Users | 2 |
| Active platform-operator accesses | 1 |
| Active organization-admin accesses | 2 |
| Organizations | 1 |
| MFA credential records | 2; not a fresh MFA/login acceptance proof |
| Employee profiles | 0 |
| Invitations | 1 pending, unexpired at the read-only check |
| Background jobs | 1 pending `invitation_email`, attempt count 0 |
| Email deliveries | 1 pending `invitation_email` |
| Menu imports / Menu Items | 0 / 0 |
| Menu Versions / Training Versions | 1 draft / 1 draft |
| Assets | 0 |

Do not repeat initial-operator creation, venue bootstrap, Admin provisioning, migrations or
grants from the older runbook. These counts establish existing setup, not the identity of each
human or a complete Employee account. Review the existing invitation through the authorized
Admin UI before any delivery; do not create a duplicate or silently broaden recipient scope.

## Worker and email preflight

Worker has all 11 expected variable names. Secret values remained masked; Resend key is sealed.
The visible reference edge points from worker to API. Presence is not proof of resolved secret
equality, provider permissions, or a successful worker connection.

Verified non-secret values: staging; public app origin
`https://web-staging-4268.up.railway.app`; sender `onboarding@resend.dev`; worker identity
`horeca-staging-worker`; idle 1 second; heartbeat 15 seconds.

Verified settings: source-less service; `/backend`; Dockerfile builder and `Dockerfile` path;
`python -m app.worker`; no pre-deploy step; no public endpoint; no HTTP healthcheck; no cron;
serverless off; On Failure / 3; existing 8 vCPU / 8 GB replica ceilings. These ceilings are not
measured consumption or an applied monetary budget.

Resend API-key metadata shows the named HoReCa key with **Full access** and **No activity**.
The sealed Railway value was not compared to that key. Review or replace it with the intended
sending-only credential through the owner's private input channel before rollout; do not copy
credentials into this repository or chat. Current test sender/recipient constraints remain.

Starting worker is not an idle infrastructure check: it can immediately claim the existing
pending invitation and send an email. Deployment and that concrete recipient/send boundary
therefore need explicit authorization. Do not run `app.worker` as a preflight command.

Prepared deployment command, only after those gates are satisfied, from the verified isolated
`outputs/staging-candidate-0956e7b-preflight/source` directory:

```powershell
rtk railway up . --path-as-root --project 04320f63-ab40-426f-ab35-02fcb365c3b8 --environment d8e64109-9863-4faa-a45e-f072adb3cfac --service 5028af74-ea48-4c31-97d7-042ae0c5836d --detach --message "CRA-122 worker candidate 0956e7bb1af8914b94bc064e65e6cfaf4f88a775"
```

Recheck queue, invitation validity, settings and artifact immediately before execution. Capture
deployment ID, startup result, job attempt/status and provider acceptance without logging
recipient/token data. Provider acceptance is not proof of mailbox receipt. On failure inspect
classified errors and actual state before retrying; do not reset jobs or revoke credentials.
Keep all five crons suspended until their individual initial-run boundaries are reviewed.

## Storage preflight and prepared correction

API has all 17 expected variables. Fresh safe-value read confirms `APP_ENV=staging`, exact web
CORS origin, Secure cookies, SameSite lax, S3 virtual addressing and region auto.

Using the running API's configured S3 client with five-second connect/read timeouts and no
retries: HeadBucket returned 200; GetBucketCors returned 200 with **zero rules**. A separate
OPTIONS request to the application-generated upload target returned 200 with no allowed-origin
or POST permission for the staging origin. No object upload, download, mutation or signed URL
disclosure occurred. Credentials remained inside the deployed process.

The Admin UI uses a cross-origin FormData POST and reads its response before completing an
asset. Missing CORS is a concrete unresolved boundary for that upload flow. OPTIONS alone does
not reproduce a complete browser upload or prove PutObject/GetObject authorization.

The [proposed CORS JSON](staging-cors-proposal.json) allows only the existing staging origin,
GET/HEAD/POST, Content-Type and a five-minute preflight cache. It does not make the bucket public
or change object permissions. Before applying, reread current rules: if changed, preserve them
and review the delta instead of overwriting. Apply to the existing `learning-assets` bucket
only after provider-configuration authorization; no API redeploy is required solely for CORS.
Then repeat OPTIONS and perform one separately approved synthetic image upload/finalization/
authorized read/anonymous denial journey. No customer photos are needed for that check.

## Content and first walkthrough

The existing 308-item import passes current `MenuImportCreate`, with 201327 canonical bytes
(below 2 MiB), 6 sections, 32 categories and 3 duplicate-name groups requiring review. The
existing source/schema/artifact digests match. No source fields were invented or refreshed.
All 5616 source/artifact checks passed. The previous 2162 import checks remain dated evidence;
only schema, size, counts and digests were freshly checked in this continuation.

Use the entire existing menu import, then initially author `lesson-01` through `lesson-04` from
the prepared local transfer plan: 27 distinct items and 54 distinct item/family pairs. This
meets local quantity targets, not server readiness. Preserve 24 multi-variant null prices,
unknown descriptions/components/allergens and snapshot provenance. Do not infer safety facts.

1. Existing Admin signs in normally; inspect exact Organization/Location and current empty draft.
2. Create Menu Import; review duplicate-name findings by source identity; confirm Draft; check
   readiness and publish. Record actual source-key-to-UUID mapping from responses.
3. Use the existing Training draft, bind its exact Published Menu Version, add the four lessons
   and source-backed blocks with current revisions. Publish after readiness review.
4. Generate candidates through existing server APIs; review category/description candidates;
   approve and publish eligible questions. The offline question bank is not a bulk API format.
5. Configure/check Interactive, Practice and Final readiness before assigning Training.
6. Employee accepts the existing valid invitation, completes profile setup and receives explicit
   Admin activation plus assignment. Reading alone does not fabricate Completion.
7. Complete all assigned lessons; Interactive uses 5 questions; Practice uses 10 distinct items
   and >=4 correct earns Final eligibility; Final uses 20 questions with explicit finish.
8. Admin verifies assignment progress, Results and Dashboard; refresh and re-login preserve
   truth. Include wrong answers, interrupted attempts and resumption. A four-lesson result
   proves the subset journey, not training coverage of all 308 menu items.

No import, publication, assignment, Employee setup, mail send or hosted authenticated journey
was performed by this preflight. Full-menu lessons follow only after the first real walkthrough.

## Fresh verification

| Check | Passed | Failed | Skipped | Limit |
| --- | ---: | ---: | ---: | --- |
| Focused backend PostgreSQL/unit suites | 76 | 0 | 0 | Provisioning, MFA/bootstrap, import/publication, Practice families, readiness, worker and storage |
| Full Vitest | 89 | 0 | 0 | 24 files; mocked API boundaries |
| Full Playwright | 69 | 0 | 0 | Three configured viewports; mocked APIs, local Vite |
| Deployment-artifact/topology tests | 5 | 0 | 0 | Static checks; not a deployment |
| Content/source integrity | 5616 | 0 | 0 | Artifacts, not application tests |

Commands: existing guarded `.harness/TESTING.md` loader followed by pytest on
`test_provision_access.py`, `test_provision_access_cli.py`, `test_bootstrap_venue.py`,
`test_auth_mfa_rbac.py`, `test_menu_import_api.py`, `test_menu_publication_api.py`,
`test_practice_reference_families.py`, `test_assessment_readiness.py`,
`test_worker_composition.py`, `test_private_storage.py`, with `-q -p no:cacheprovider`;
`rtk pnpm test --maxWorkers=2`; `rtk pnpm test:e2e`;
`rtk proxy node --test frontend/deployment-artifacts.test.mjs .railway/topology.test.mjs`;
`rtk proxy py -3.12 -X utf8 outputs/demo-content-full/verify_package.py`.

Initial backend shell quoting failed before pytest; corrected invocation passed. Initial Vitest
could not start under sandbox EPERM; permitted retry passed unchanged. Full backend coverage,
Docker builds, live email, object writes, cron execution, backup/restore and load were not run.
No new production-code defect or contract change is claimed. Linear retains its older snapshot
until a separately authorized synchronization; fresh runtime evidence must not be mistaken for
new product policy or acceptance.
