# HoReCa Repository Status

## Local source checkpoints completed — 2026-09-21

Denys authorized the four-entry selective local commit map after reviewing the audit.
CRA-237 is committed as `25917f2`, CRA-238 as `381c288`, and CRA-240 as `62b0144`.
This documentation checkpoint completes the fourth entry. These commits have not been pushed;
the last verified remote baseline remains `9d68d9d`. No hosted operation or acceptance change occurred.

The Prettier failure was CRLF line endings in `AdminTrainingPage.test.tsx`. Converting them to
LF changed no text or logic; the normalized before/after contents are identical. Global Prettier,
lint and typecheck now pass; the focused picker/editor rerun passed 16 tests, zero failed/skipped.
The earlier same-session 125 backend, 128 frontend and six browser tests remain applicable:
implementation content is unchanged. The sealed CRA-234 candidate is unchanged and still awaits
separately authorized delivery. Full staging and owner acceptance remain open.

See [the completed commit map and verification ledger](docs/testing/reconciliation-2026-09-21.md).
The dated preparation section below records the state before local-commit authorization.

## Source and acceptance reconciliation — CRA-122, 2026-09-21

Denys authorized completing the audit follow-up that does not require his participation.
Current source/delivery/acceptance matrix, exact future selective commit map and fresh checks:
[September 21 reconciliation](docs/testing/reconciliation-2026-09-21.md).
Local main, origin/main and the directly queried GitHub main match `9d68d9d`.
CRA-237/238/240 are delivered but remain uncommitted in this checkout; CRA-234 is published in
Git but remains excluded from the latest recorded deployed API. The index is empty.

The original CRA-271 397-file source/ZIP was hash-verified. A separate 399-file candidate adds
only CRA-234's six immutable source/test paths while preserving delivered fixes. It has not
been uploaded or deployed. [Exact candidate and API-only delivery plan](docs/deployment/security-fixes-cra-234-delivery.md).

The September 17 Employee/mobile/password-reset evidence and persisted 95% Final result supersede
older missing-Employee-session instructions. Menu/Training and 80-question publication are already
complete; do not repeat them. Full staging acceptance and Alexandra's venue/content sign-off
remain distinct. Unknown composition/allergens remain unknown; the complete fact-review editor,
new-format question publication, email digests and operational pilot gates remain separate.

No product behavior, dependencies, hosted state, issue acceptance state or Git history changed
in this reconciliation. Checks and limitations are reported in the linked ledger; earlier dated
checkpoints below retain their original evidence and do not authorize repeating completed actions.
Fresh verification: 125 backend tests, 128 Vitest tests and six three-viewport browser checks
passed, zero failed/skipped in those runs. Ruff, mypy, frontend lint/types/build pass. Global
Prettier still flags the pre-existing AdminTrainingPage.test.tsx formatting difference.
Six Linear issues and three navigation documents were synchronized without acceptance changes.

## Deployed demo UX correction — CRA-271, 2026-09-17

Denys authorized deployment after commit/push through `9d68d9d`. Migration 0020 and scoped
runtime privileges are applied; API `adffd5f0-2675-4ca7-916a-9b3f1d8627de` and web
`82941686-422a-4f05-a09d-c03ce43e26e5` are SUCCESS. The isolated source preserves deployed
CRA-237/238/240 and excludes unrelated CRA-234; raw Git HEAD was not deployed.

Exact candidate checks: 32 backend and 22 frontend tests passed, zero failed/skipped;
TypeScript/Vite build passed. Eight public HTTP checks passed. Live Admin history/results/
answer review and certified Employee Home were verified; existing 95% / 19-of-20 result remains.
No question republication, content edits, email sends, worker/cron rollout or extra Git actions.
History starts with new manual Draft edits; smaller question option sets require separately
reviewed publication. Earlier local-only/no-deploy wording below is historical.
[Deployment evidence](docs/deployment/demo-ux-cra-271.md).

## Local demo UX correction — CRA-271, 2026-09-17

Denys reported successful Employee/mobile/password-reset acceptance and supplied a passed
Final Exam screenshot (19/20, 95%). The earlier lack-of-Employee-session checkpoint below is
historical; this is owner-reported evidence, not a fresh automated staging acceptance run.

Authorized local fixes now cover certified Home, bounded single-answer description questions
for new generation, return from Menu to the originating lesson, concise exam summary/error
review, richer Admin Results and separate Menu business change history with actor-email
snapshots and before/after values. Technical Operator audit is preserved. Migration 0020
was applied only to the dedicated test database; no deployed data or existing attempts changed.

Final combined backend verification: 61 passed, 0 failed/skipped. Frontend full suite with two
workers: 124 passed; additional focused final run: 20 passed (overlapping, includes four new
return-path checks). Browser checks: 6 passed across desktop/compact/mobile. Ruff, mypy,
frontend lint and build pass. One pre-existing unrelated frontend formatting difference
remains; initial failed runs and recovery are recorded in the report.

Follow-up: Denys explicitly authorized six selective CRA-271 commits and push to origin/main.
Fresh origin has no divergence and is 32 commits behind the previous local checkpoint;
normal publication includes that existing ancestry. Unrelated dirty changes remain excluded.
No deployment is authorized. Existing Published questions retain their old option counts;
new-bank review/publication and email notifications remain separate actions. Evidence is in
[CRA-271 evidence](docs/testing/demo-ux-followup-2026-09-17.md).

## Reviewed question publication — CRA-239, 2026-09-17

Denys authorized autonomous continuation of the audited demo plan. All 80 existing candidates
were checked against the 308-item Published Menu v1 and published once through normal Admin
batch approval. The UI confirmed `80` approved and an empty needs-review queue. Fresh readiness
shows **4/4 lessons ready** (pools 10/24/24/22, minimum 5), **Practice 27/10 distinct menu items**
and **Final 80/20 questions**, with rotation supported for all scopes. Unknown structured
composition/allergen facts remain unknown; the demo bank covers 27 distinct source items.

The existing active Employee already has Published Training v1 assigned, with 0/4 required
lessons complete. No duplicate assignment or activation was created. Both available browser
profiles have Admin sessions; no authenticated Employee session was available. Learning,
Interactive, Practice, Final and Results acceptance therefore remain unexecuted, not passed.
Next: ordinary Employee sign-in, then the assigned journey and owner walkthrough acceptance.

This continuation changes operational question state and two documentation files only; no
application code, deployment, dependency, migration, local commit or push. Earlier dated
unapproved-question/readiness-blocker statements below are historical.
[Review, verification and next-step evidence](docs/testing/demo-continuation-2026-09-16.md).

## Hosted correction — CRA-240, 2026-09-16

Owner-approved API deployment c346bfcb-8526-4c56-b399-0daed5154c75 is SUCCESS.
Fresh Admin refresh and API logs confirm all three assessment-readiness endpoints return 200;
public API health returns 200 (4 HTTP checks passed, 0 failed/skipped). Question Bank loading
error is resolved. Existing 80 candidates remain unapproved; Practice 0/10 and Final 0/20 are
blocked by insufficient published questions. No configured lesson assessments yet.
[Delivery evidence](docs/deployment/readiness-fix-cra-240.md). Next: review existing candidates,
then separately approved publication and Employee journey. No regeneration, Git commit or push.
Earlier local-only and hosted-failure checkpoints below are historical.

## Local correction — CRA-240, 2026-09-16

Denys approved the local lesson-readiness fix after the CRA-239 failure. The PostgreSQL
regression reproduced two null lesson UUID validation failures; the query now selects only
interactive_training assessments. Relevant combined verification: 67 passed, 0 failed/skipped;
Ruff format/check and strict mypy pass. [Scope, evidence and commit boundary](docs/testing/interactive-training-readiness-cra-240.md).
No commit, staging data write or deployment. Hosted recovery remains unverified and CRA-239
remains blocked pending separately approved delivery. Existing 80 candidates remain unreviewed;
do not regenerate them. The preceding audit checkpoint below describes the unchanged hosted state.

## Current checkpoint — after Training publication, 2026-09-16

Denys requested the audit follow-up in order. This is documentation reconciliation under CRA-122;
no new code, Git commit, push or deployment is performed by this checkpoint. The earlier audit
inferred pending CRA-238 delivery from an outdated report. Subsequent source and browser checks
established that delivery and Training publication had already completed in the preceding task.

| Boundary | Latest evidence and limit |
| --- | --- |
| Menu | CRA-237 records Published Menu v1 from the 308-item snapshot. Unknown composition/allergen facts remain unknown; demo publication is not fact certification |
| Training | Fresh authenticated `/admin/content` read shows Published v1 and no Draft. The preceding approved operation records four required lessons for Ofitsiant, 88 blocks and 40 menu-card occurrences |
| Questions | CRA-239 generated 80 candidates, 0 existing and 0 stale. None approved/published. Subsequent lesson readiness returns HTTP 500 twice; Practice/Final reads return 200. UI retains stale pre-generation readiness, so displayed 0/0 and `ASSESSMENT_NOT_CONFIGURED` are not current backend readiness evidence |
| Delivery | API remains the sealed CRA-237 candidate; web CRA-238 delivery is recorded successful. Fresh public HTML returns 200 and references `index-DEGtw7P2.js`, matching the CRA-238 smoke record. Worker has its separate earlier delivery |
| Source | Local `main@bf4790c` is 32 commits ahead / 0 behind directly verified GitHub `fafec73`. CRA-237/238 source is uncommitted; CRA-234 is committed locally and excluded from those deployed packets |
| Harness | Direct upstream main equals pinned `3eaa9586b4e09e70399c2600aa1808b18449a15d`. No rule or pin change is needed |
| Acceptance | Existing Employee activation is recorded complete. Assignment, Employee assessment journey and Results acceptance remain unproven; no full regression or pilot acceptance is implied |

Evidence: [CRA-237](docs/testing/menu-demo-publication-cra-237.md),
[CRA-238 and hosted continuation](docs/testing/training-menu-picker-cra-238.md),
[ordered next steps and reconciliation checks](docs/testing/demo-continuation-2026-09-16.md).
Do not recreate lessons, reimport Menu, repeat activation or redeploy CRA-238 from old checklists.

Next: reproduce and correct the bounded lesson-readiness failure before further publication;
continue source/answer review of the existing 80 candidates without regenerating them,
publish only reviewed questions, verify 5/10/20 readiness, inspect the existing Employee's
assignment state, then complete Learning, Practice, Final and Results. Preserve unknown facts.
CRA-234 delivery and GitHub publication retain their separate release boundaries. Real uploads,
recovery-provider checks, cron acceptance, load, isolated restore, accessibility and venue UAT
remain wider staging/pilot gates.

<details>
<summary>Earlier September 16 checkpoints — superseded by the current checkpoint</summary>

## Latest delivery — CRA-237, 2026-09-16

After the user confirmed the menu import, readiness exposed unknown-fact publication blockers.
CRA-237 now implements grouped findings and explicit non-production demo publication while
preserving unknown facts and strict ordinary/production rules. Denys subsequently approved
the isolated API/web rollout and existing Draft demo publication. Both deployments succeeded;
the authenticated Admin UI now shows Published Menu v1. The imported snapshot has 308 items.
No reimport, fact confirmation, worker/cron/configuration/migration or Git operation occurred.
CRA-234 remains excluded from the delivered candidate.
Verification and exact source boundary: [CRA-237 report](docs/testing/menu-demo-publication-cra-237.md).
The [fact-confirmation workflow](docs/testing/menu-fact-confirmation-workflow.md) defines the
next source-based review process; the full confirmation editor remains future bounded work.
The older empty-menu state below predates the user's successful Confirm-to-Draft action.


## Current product and source checkpoint — 2026-09-16

Denys authorized the audit reconciliation, Linear updates and six selective local commits.
The complete map, current verification and exclusions are in
[September 16 reconciliation](docs/testing/reconciliation-2026-09-16.md).

| Boundary | Current evidence |
| --- | --- |
| Product access | Authenticated Admin UI shows one active Employee, zero pending activation and zero assignments/certifications. Do not repeat provisioning, activation or invitation resend |
| Content | Menu Draft v1 has zero items; Training Draft v1 has zero lessons, no selected Waiter audience and no Published Menu binding. Question generation remains blocked by unpublished sources |
| Delivered application | September 15 CRA-233 report records successful API/web rollout and one Delivered invitation; worker uses the verified-domain sender. This is dated provider evidence, not a new provider inventory |
| CRA-233 source | Backend `80c0996` and UI `58ad81f` locally committed; sealed 384-file deployment packet reverified with no hash mismatches or extras |
| CRA-234 source | Recovery `3b3c79a` and body boundary `0f767a6` locally committed. These corrections are absent from the deployed CRA-233 packet and require separate delivery |
| GitHub and Harness | Direct GitHub main remains `fafec73`; no push. Global Harness remains clean at pinned `3eaa9586b4e09e70399c2600aa1808b18449a15d`; no rule or pin update |
| Acceptance | CRA-122 and open feature issues retain their existing status. Accepted CRA-123/125/126 gates are historical acceptance, not a new full regression or pilot approval |

Next product work is reviewed Menu publication, Waiter audience and exact Menu binding,
four lessons, reviewed Published questions with 5/10/20 readiness, then assignment and the
existing Employee journey through Results. The prepared offline content is input material,
not proof of server readiness. Content writes, CRA-234 rollout and GitHub push remain separate.
Real uploads/recovery-provider checks, cron acceptance, load, isolated restore, accessibility
and Alexandra's UAT remain wider pilot gates.

The September 15 worker/source/pending-invitation summaries are retained below as dated history.
Linear receives a brief reconciliation update; automatic approval rejected the detailed external
metadata update. This repository ledger retains the full evidence without changing contracts.
Photos, outputs, other worktrees and the pre-existing metadata-only question-generation mark
are preserved. No production code was edited during this synchronization.

</details>

<details>
<summary>Historical checkpoints — not current instructions</summary>

## Latest delivery — CRA-233, 2026-09-15

Denys approved the sealed invitation list/resend candidate deployment and one controlled send.
API `e3297673-0ae5-428a-b94a-085c0d80a2fc` and web
`7875de0b-c9b8-4f09-b812-14f72874e560` are SUCCESS. The prior worker update
`7eba759c-d82c-46f8-8067-c4d77d7a1d6b` uses the verified-domain sender.
The existing expired invitation was resent through the authenticated Admin UI; new job completed
on its first attempt, and Resend confirms Delivered. No recipient/token is recorded here.

Five final live HTTP checks passed. Earlier local gates: 21 PostgreSQL, 10 Vitest and 3 Playwright
passed; no full coverage rerun. No commit/push/migration or cron rollout. CRA-233 source is still
uncommitted; reproduce delivery from its sealed 384-file packet, not plain HEAD or dirty root.
Exact scope, archive hash, IDs, checks and limitations: [Admin invitation resend](docs/testing/admin-invitation-resend.md).
Next: recipient acceptance, Admin profile setup and explicit Employee activation. The older
worker/source/unsent state below is superseded by this checkpoint.

## Current checkpoint — 2026-09-15

Denys authorized the audit follow-up: reconcile already deployed CRA-172 into the main checkout
and clean local context routing, then explicitly authorized the three selective local commits.
The source checkpoints are `6c29708` (backend) and `19e7f19` (UI and evidence); this documentation
checkpoint is the third approved boundary. No push, Linear write, deployment, provider send,
migration or non-test data operation occurred in this follow-up.

| Boundary | Verified state |
| --- | --- |
| Local Git | Source checkpoint `main@19e7f19` follows `d88cb61` with two recovery commits; this documentation commit follows it. GitHub was directly checked at `fafec73`; no push in this series |
| Local source | Six CRA-172 recovery files are committed through `19e7f19` and match the sealed CRA-202 delivery packet, including the preserved audience editor |
| API/web delivery | September 15 report and CRA-202 record SUCCESS: API `e70807b3-36c7-4cc1-bc00-462dc7c56806`, web `d2424c99-eaed-4251-a1cb-355521a10e1a`; this is recorded delivery evidence, not a fresh provider check |
| Deployed source | 380-file `d88cb61` export plus the six-file CRA-172 overlay; local recovery source is now committed, but a new deployment candidate still needs exact manifest verification and approval |
| Worker | Last recorded deployment `aad4336b-ebdf-413b-a1e3-4a4bf46dfc76` from `0956e7b`; not redeployed with September 15 email-copy fixes |
| Resend | DNS connected according to Denys on September 15; sender, invitation expiry/job state and successful real delivery still require verification |
| Data and storage | Existing provisioning/migrations/grants and September 13 scoped CORS are recorded completed; do not repeat them from old checklists. Content publication, Employee acceptance and real upload remain unproven here |

Fresh reconciliation: **51 PostgreSQL tests, 17 UI tests and 3 browser tests passed**, with zero
failures/skips in final GREEN runs. Backend RED was the intended 404; UI RED was the absent
recovery button. Full backend coverage and full browser regression were not rerun.
Exact files, static checks and limits: [source reconciliation](docs/testing/training-source-reconciliation.md).
The [audience report](docs/testing/training-audience-editor.md) records earlier implementation
checks; overlapping test counts must not be summed.

### Next bounded steps

1. Reconcile canonical Linear navigation with the current delivery facts through an authorized external update.
2. Verify worker sender/source and invitation/job state; prepare a concrete worker release and one controlled
   mail/Employee acceptance path. DNS verification alone is not email-delivery evidence.
3. Complete reviewed Menu/Training content publication and the real Admin → Employee → Results journey,
   followed by Alexandra's acceptance. Real writes, sends and deployment remain separate operations.

CRA-122 and the relevant acceptance issues remain open. Linear START HERE/CRA-122 still contain
older delivery summaries; CRA-202 has the newer September 15 execution record. Read the latest dated
evidence and accepted decision before acting; this local update does not change product contracts.
Worktree 54bf, Photos, runtime artifacts and unrelated uncommitted changes are preserved.


## Authorized worker and CORS execution — 2026-09-13

The [execution checkpoint](docs/deployment/staging-preflight-2026-09-12.md) supersedes the
preparation-only state below. Denys authorized the prepared operations. Worker deployment
`aad4336b-ebdf-413b-a1e3-4a4bf46dfc76` from immutable 0956e7b reached SUCCESS and is Online.
Scoped staging bucket CORS was applied and read back; approved-origin OPTIONS passed and
unrelated-origin OPTIONS was rejected (2/2 expected results). No upload was performed.

The existing Resend key now shows Sending access. Existing invitation delivery was attempted
but rejected with HTTP 403: onboarding@resend.dev permits only the account-owner test recipient.
No accepted send was observed; existing bounded retries remain active at the last inspection.
No verified sending domain exists. Next owner decision: choose and verify a sending domain,
or explicitly select the account-owner test-recipient route. Employee acceptance and menu
publication remain open. No application/index changes, commits, push or other service deploys.

## Fresh staging preflight — 2026-09-12

The [read-only preflight and next-operation packet](docs/deployment/staging-preflight-2026-09-12.md)
supersedes the September 11 **account-state** snapshot below: staging already contains two
Users, one active platform access, two active organization-admin accesses and one Organization.
Do not repeat provisioning/bootstrap. Employee profiles remain zero; one invitation and its
email job are pending, with zero attempts. Menu and Training each have one draft; no Menu
Items/imports or Assets exist. These are aggregate reads, not authenticated user acceptance.

API/web/PostgreSQL are online; migration completed; worker and five crons offline. Worker
settings and all expected variable names are present. Starting it can immediately send the
pending invitation. Resend named-key metadata still shows Full access and no activity.
S3 HeadBucket and GetBucketCors return 200, but zero CORS rules and a real OPTIONS response
without staging-origin/POST permission leave browser upload unresolved. A scoped CORS proposal
is prepared, not applied. Secrets remained masked and no provider/data mutation occurred.

Fresh gates: 76 focused backend, 89 Vitest, 69 Playwright, 5 static delivery/topology and 5616
content checks passed, zero failed/skipped in final runs. Full backend coverage was not rerun.
The 377-file isolated 0956e7b export and ZIP still match their manifest. Existing content can
support a proposed first four-lesson journey (27 distinct items / 54 item-family pairs), subject
to actual generation, review, publication, readiness and assignment.

Next owner boundary: review existing invitation recipient and mail credential scope, authorize
the concrete worker deployment/send and CORS operation, then complete the normal Employee
invitation/login path. Code, Git index and external state remain unchanged by this preparation.

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

## Verified staging checkpoint — 2026-09-11, after API rollout

This checkpoint supersedes older current-state and next-action wording below. Denys authorized
this reconciliation and preparation of the next delivery step under CRA-122; this update does not
perform a commit, push, deployment, account creation, email send or database mutation.

- Local main is `0956e7bb1af8914b94bc064e65e6cfaf4f88a775`, including the completed CRA-171
  provisioning commit after `ede4281`. Direct GitHub main remains `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`:
  ahead 17, behind 0. Do not recreate or recommit the completed implementation maps.
- The executed migration/API delivery used the isolated `0956e7b` source export (377 manifest
  files), not the dirty worktree or GitHub main. This records the executed artifact; remaining
  service deployments and feature acceptance retain their own gates.
- The preceding owner-approved task records successful execution of all 19 migrations through
  `0019_auth_security_budgets`, verification of all 84 application tables, and runtime DML grants
  on 84/84 tables with zero excess privileges. Runtime has no schema CREATE or migration-table
  access. These SQL results are recorded evidence, not a new SQL run in this reconciliation.
- Fresh read-only Railway metadata confirms API deployment
  `7cacd4d9-dfed-45de-a68b-e686f1ecab9d` is SUCCESS and not stopped; PostgreSQL is also SUCCESS
  and not stopped. The latest migration deployment `ad1bdb6c-b8e6-47ac-97e9-b9ef1a843154` is
  SUCCESS and stopped. Worker, web and all five cron services have no latest deployment;
  all five schedules remain null.
- The preceding task recorded API health 200 and clean startup. The health handler does not query
  the database; the separate successful database probe is recorded below. Storage and complete
  real-origin acceptance remain unproven. The first failed migration report is historical.
- CRA-131 and CRA-123–126 are Done. CRA-147–151, CRA-170 and CRA-171 retain their existing
  In Progress acceptance boundaries. No non-test account provisioning is recorded.
- Recorded local verification remains 865 backend / 89 Vitest / 69 Playwright on September 10,
  plus the later 29 focused CRA-171 tests, all with zero failures/errors/skips in their final runs.
  The suites overlap and must not be added. Full coverage predates CRA-171 and was not refreshed.

Fresh continuation: CLI SSH timed out before SQL. The private browser console of the running API
then passed a read-only SQL probe using its deployed Settings/DATABASE_URL: expected database and
runtime identity match; transaction read-only is on; users SELECT is allowed; schema CREATE is
denied. No credentials or application rows were printed and no database writes were performed.
This closes API-to-database connectivity, not storage, authenticated requests or full acceptance.

Web preparation: all 377 exported files still match the manifest, with zero extra files or hash
mismatches. Five static delivery/topology tests passed, zero failed/skipped, after the first attempt
could not spawn two test files under the Windows sandbox (EPERM; no assertions ran). The 13-file
documentation package has 212 checked relative file links, zero broken. Full product suites were
not rerun. See [the exact web rollout proposal](docs/deployment/cra-122-source-build-preparation.md#web-rollout-proposal--2026-09-11).

Next: obtain web rollout approval for the verified source/settings; then complete
worker/provider/storage prerequisites, guarded accounts, approved content publication and
Admin/Employee real-origin acceptance.
Do not repeat completed migration, role creation, password changes or grants from historical lists.

### Reconciliation file and commit boundary

One proposed selective checkpoint: `docs: reconcile staging API rollout and prepare web delivery`.
Only this continuation's navigation/evidence/proposal hunks belong to it; local commit permission
has not been granted and the Git index remains empty. Earlier dirty documentation stays separate.
Paths: `STATUS.md`, `CONTEXT.md`, `README.md`, `backend/README.md`, `docs/architecture/README.md`,
`docs/testing/README.md`, `.harness/GIT-WORKFLOW.md`, `.harness/TESTING.md`,
`docs/deployment/staging-cra-122.md`, `docs/deployment/staging-acceptance-cra-122.md`,
`docs/deployment/cra-122-source-build-preparation.md`, `docs/testing/account-provisioning.md`,
`docs/testing/demo-candidate-2026-09-10.md`. Verification: relative links, exact diff/inventory,
unchanged index/runtime sources, provider readback and the five static delivery/topology tests.
No API, schema, RBAC, dependency or test-threshold contract changed.

## CRA-171 local account provisioning — 2026-09-11

Protected one-time operator and separate Organization Admin setup is implemented locally.
See [scope, exact commands, RED/GREEN evidence and execution boundary](docs/testing/account-provisioning.md).
Final focused real-PostgreSQL/CLI/bootstrap/MFA gate: 29 passed, 0 failed/errors/skipped.
Ruff format/check and strict mypy pass. No public API, schema or dependency change.
One selective local commit is authorized; no non-test accounts, email, push or deployment.
CRA-171 remains pending owner acceptance.
The 865-test coverage snapshot below predates this new operation and has not been rerun for it.


## Current checkpoint — 2026-09-11

The local demo implementation is committed through `ede4281` (16 checkpoints ahead of
GitHub `fafec73`, behind 0; direct remote read September 11). The exact ledger and recorded
September 10 verification are in [the candidate report](docs/testing/demo-candidate-2026-09-10.md).
Recorded final gates: 865 backend, 89 Vitest and 69 Playwright passed, zero failures/errors/skips;
93.96% statements, 80.46% branches and 89.77% fixed critical aggregate. These are not new test runs.

Denys accepted CRA-131's current public-page visual iteration on September 11; copy refinement
and additional animation are deferred. CRA-123–126 remain accepted and Done. Other local
implementation acceptance remains distinct from completed commits and staging delivery.

The accepted account direction is protected one-time provisioning of a separate technical
operator and Alexandra's Organization Admin account. Alexandra uses existing email invitations
for employees. An owner provisioning cabinet is deferred. No new operational role is implied.

Fresh September 11 Railway read: PostgreSQL has one active successful deployment; nine application
services have no source or deployment; five cron schedules are null. Pending settings count is
unavailable. Selected staging SHA remains `fafec73`; replacement selection and rollout are separate.
No application code, Git index, commit, push, deployment or non-test data changed in this
documentation synchronization. Older current-state wording below is historical where superseded.

## Local implementation commits complete — 2026-09-10

The six CRA-131/147/149/150/151/170 maps are committed locally under Denys's explicit
authorization. See the [commit ledger, verification and next staging steps](docs/testing/demo-candidate-2026-09-10.md).
The final source snapshot matches all 354 recorded candidate hashes: full backend 865 passed;
final frontend 89 Vitest and 69 Playwright passed; all final successful runs have zero
failures/errors/skips. Focused staged checkpoints and quality checks also passed.
Earlier uncommitted/no-authorization statements below are historical and superseded for
this mapped series. Feature acceptance, publication and staging delivery remain separate.
No push, Linear write or deployment occurred; the selected staging SHA remains `fafec73`.
Unrelated local documentation, preparation drafts, Photos and runtime outputs are preserved.


## Candidate verification complete — 2026-09-10

CRA-122 local preparation is recorded in the
[candidate verification and selective publication map](docs/testing/demo-candidate-2026-09-10.md).
Frontend Vitest 89, Playwright 69, delivery artifact 2 and Railway topology 3 tests passed,
with zero failures/skips; build, format/lint and topology typecheck passed. The fresh full backend
retry passed **865 tests, 0 failed/errors/skipped**. Statements **93.96%**, branches **80.46%**,
fixed critical aggregate **89.77%**: all gates pass. Test-DB Alembic is at 0019 with no drift.
The initial run had 16 Windows temp setup errors and failed coverage persistence; it is not
included in the successful report. The permitted retry changed execution conditions only.

Fresh Railway status: PostgreSQL has one active successful deployment; nine application services
have no active/latest deployment or repository/image source, and five cron schedules are null.
Public `/healthz` returns Railway 404. Candidate acceptance, immutable delivery, account
provisioning and live acceptance remain open. No commit, push or deployment occurred.

## Local security corrections — CRA-170 — 2026-09-09

Both September 9 Codex Security findings are fixed locally: password change revokes prior unused
reset tokens atomically; public rate-limit state has a 4096-row cap per table with bounded,
concurrency-safe expiry reclamation. Existing exact-subject limits and MFA remain enforced.
At saturation or admission-lock contention, new subjects can receive `429 AUTH_RATE_LIMITED`.

Final focused PostgreSQL regression: **124 passed, 0 failed, 0 errors, 0 skipped**. Backend Ruff
format/check (254 files), strict mypy (232 files), and diff hygiene passed. One independent review
identified a mixed-action reclamation regression; both variants were reproduced and corrected
before the final run. Full product coverage/browser/provider checks were not refreshed.

[Exact scope, RED/GREEN evidence, file/commit map and limitations](docs/testing/security-fixes-cra-170.md).
CRA-170 remains In Progress pending owner acceptance. No commit, push, deployment, new dependency,
schema change or non-test data mutation. The selected published SHA below does not contain these fixes.

## Current local work — 2026-09-09

Documentation synchronization: Linear START HERE, two-person demo, CRA-122, CRA-131/147/149–151
and the FINAL API implementation addendum reflect the current local outcomes and remaining gates.
CRA-148's accepted offline transfer projection stays separate from actual server import/publication.
See [testing index](docs/testing/README.md) for shared verification; previous counts are historical.

Published/selected staging source remains `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`, schema
`0019_auth_security_budgets`. CRA-123–126 are accepted and Done. New local work is uncommitted
and cannot be included in that SHA. Earlier pending-acceptance wording below is historical.

- CRA-149 implements the accepted category/description Practice extension; see
  [scope and test evidence](docs/testing/practice-reference-families.md).
- CRA-131 public entry and CRA-147 Employee profile remain local review candidates. September 9
  audit reran frontend gates: 83 Vitest and 60 Playwright passed, zero failed/skipped, plus
  format/lint/typecheck/build. Browser APIs are mocked; these are not hosted results.
- CRA-148's offline content is review material. Server generation and Admin publication remain
  necessary. Customer sources and generated artifacts stay outside Git.
- CRA-150 implements [logout of other devices](docs/testing/logout-other-devices.md), preserving
  the current session. CRA-151 implements the [Admin Dashboard](docs/testing/admin-dashboard.md)
  with scoped aggregates and location filtering. Both are local, pending owner acceptance.
- Backend focused gates: Practice 101 passed; logout 33 passed; Dashboard/access 24 passed;
  zero failures/skips in those final runs. Ruff check/format and strict mypy (230 source files)
  pass. This is not a new full backend suite or coverage gate.
- Final frontend Vitest: 89 passed across 24 files with `--maxWorkers=2`, zero failed/skipped.
  Final shared Playwright run passed (`test-results/.last-run.json`: passed, no failed tests;
  69 configured cases). Production build, frontend format check and ESLint pass.
  Final `git diff --check` passes; the Git index remains empty.
- [Current staging preparation](docs/deployment/staging-acceptance-cra-122.md) distinguishes
  the completed key/reference/login preparation from unresolved delivery and live acceptance.
  The September 9 public health probe returned HTTP 404 with Railway fallback; no hosted app
  readiness is established. No provider configuration inventory refresh is implied.

No commit, push, source binding, migration, deployment or customer-data write occurred here.

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

**Snapshot date:** 2026-09-08

The next-step [acceptance and staging decision packet](docs/deployment/staging-acceptance-cra-122.md)
is prepared for CRA-123–126 and proposed candidate `fafec73` / migration 0019.
It records the ordered gates, recovery limits, live security cases and pending decisions.
The [delivery addendum](docs/deployment/cra-122-source-build-preparation.md) records the
Railway CLI/documentation check and two delivery options. No issue acceptance, candidate
selection, commit, provider mutation, migration or deployment was performed by preparing it.

## Current checkpoint — 2026-09-08

Denys authorized this repository/Linear synchronization under CRA-122 after the read-only audit.
It changes documentation and project routing only. Formal acceptance, source selection, local
commits, push, provider settings, migration, deployment and non-test data retain their own gates.

### Published code and verification

- Local `main`, tracked `origin/main` and the direct GitHub API ref match
  `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`. Ahead/behind: 0/0; Git index is empty.
- CRA-123 `ec27d19` and CRA-124 `e18af71` are published. CRA-125's ten commits end at
  `2275cee1ae46da708f33a032229e708c73a966c8`. CRA-126 adds four commits
  `6e2665e`, `0083ddf`, `034bb5c`, `fafec73`, covering exactly 22 mapped files.
- CRA-123/124/125/126 remain In Progress pending explicit formal acceptance. Published code is
  not unfinished implementation, and synchronization does not mark an issue Done.
- CRA-126's recorded full PostgreSQL 16 gate: **832 passed, 0 failed, 0 errors, 0 skipped**.
  Statements **11532/12286 (93.86%)**, branches **2064/2574 (80.19%)**, fixed critical aggregate
  **1319/1471 (89.67%)** all pass. Ruff format/check, strict mypy and test-DB Alembic checks passed.
  The audit reevaluated the saved coverage JSON successfully; it did not rerun the full suite.
- Current source migration head is `0019_auth_security_budgets`. CRA-125's 809-test result and
  `0018_job_runtime` describe the earlier candidate. September 7 frontend evidence remains
  72 Vitest tests, 42 Playwright executions and 5 artifact/topology checks; no new browser,
  container or provider result is claimed.
- Evidence: [CRA-126 security verification](docs/testing/security-fixes-cra-126.md) and
  [CRA-125 publication/coverage record](docs/testing/coverage-closure-plan.md).

### Staging and next decisions

CRA-122 is the bounded synchronization/staging-preparation task. CRA-121 remains accepted and Done.
The last explicitly accepted staging candidate is still
`2275cee1ae46da708f33a032229e708c73a966c8`. Published `fafec73` is the proposed replacement,
**not an accepted deployment candidate**. Its migration 0019, rollback/data boundary and storage
cutover must be reviewed together before any rollout.

The September 7 provider evidence records two completed settings packages: five cron schedules
suspended plus two non-secret variables, then the nine-service build/start package
(`skipDeploys=true`). Saved config says DOCKERFILE for all nine services; ServiceInstance still
reports RAILPACK, so actual builder use needs later build evidence. At that readback all nine
application services had no source/deployments and no push triggers. No fresh Railway read was
performed by this synchronization.

The September 8 source-binding investigation remains unresolved: `enabled=false / NO_REPO`
does not prove disabled autodeploy after connection. A side-effect-free preview is not proof
of suppression. The prepared Railway support question has not been sent. Do not repeat completed
settings, DB-role creation or SSH registration. Preserve existing secret material without reading
or changing values.

Next: explicit corrective acceptance; candidate/0019 rollback and storage GetObject/PutObject
review; supported source-binding/autodeploy guarantee; scoped secrets/DB LOGIN/runtime grants,
resource/cost controls and initial operator preparation; then separately approved migration,
rollout and real-origin synthetic acceptance. Dashboard/logout-all disposition remains open.
Existing owner-only test email scope persists; synthetic writes and runtime rollout are separate.
Pilot load, isolated restore, Bacara content/UAT and manual accessibility gates remain later work.
CRA-19 and protected Photos remain a separate visual track.

See the [staging plan](docs/deployment/staging-cra-122.md),
[source investigation](docs/deployment/cra-122-source-build-preparation.md) and
[live acceptance runbook](docs/deployment/staging-acceptance-cra-122.md).

### Synchronization boundaries and checks

1. `docs: reconcile published baseline and verification state`: README.md, STATUS.md, CONTEXT.md,
   backend/README.md, docs/architecture/README.md, .harness/GIT-WORKFLOW.md, .harness/TESTING.md,
   .harness/UPSTREAM.md, docs/testing/README.md, docs/testing/coverage-closure-plan.md and
   docs/testing/caddy-delivery-cra-123.md. Check exact Git refs/ancestry, dated evidence, links
   and diff hygiene. Synchronize Linear START HERE, project routing, CRA-123/124/125/126,
   CRA-13's execution pointer and the coverage-plan document without changing contracts.
2. `docs: reconcile staging preparation after CRA-126 publication`: docs/deployment/staging-cra-122.md,
   docs/deployment/cra-122-source-build-preparation.md and docs/deployment/staging-acceptance-cra-122.md;
   synchronize CRA-122 and its Stage 2 document. Check candidate versus published SHA, migration
   and rollback distinctions, recorded provider effects and unexecuted gates.

Documentation-only TDD exception: no runtime behavior changes. Verify links, exact inventory,
source/command references and diff hygiene; do not claim a new application test run.
These are selective future commit boundaries, **not commit or push authorization**.
The global harness remains pinned to `3eaa9586b4e09e70399c2600aa1808b18449a15d`;
all 31 upstream files were read and upstream main matches. No operating rule changed.
Preserve existing user documentation, the metadata-only question_generation.py mark, Photos,
outputs, JSON deployment drafts and ignored local data. Draft JSON files retain their reviewed
inputs and are not executable approval for a new candidate.

### Synchronization verification — 2026-09-08

All 14 mapped repository documents are updated. All 156 checked relative links resolve;
git diff --check passes. Application, test and migration content is unchanged, HEAD remains
fafec73 and the Git index remains empty. No application test suite was rerun.
Readback confirms all ten Linear updates: six issues (CRA-122/123/124/125/126/13), three
documents (START HERE, Stage 2 and coverage plan), and the project description. CRA-126 is
now attached to HoReCa Training Platform and retains its CRA-122 relation. Existing issue
statuses and accepted thresholds are preserved; no formal acceptance or deployment occurred.

<details>
<summary>Historical repository checkpoints through September 7 — superseded current-state wording</summary>

**Snapshot date:** 2026-09-07

**Latest CRA-122 decision:** Denys accepted `2275cee1ae46da708f33a032229e708c73a966c8`
as the exact candidate for all nine staging application services. Recorded in CRA-122 and
its Stage 2 document; full Stage 2 remains open. Denys subsequently approved the five-cron
schedule suspension plus application of the two non-secret variables with skipDeploys=true.
Patch ee4d02d2-388d-46cd-a7be-49f30046b42c is COMMITTED at 2026-09-07T17:57:57.075Z;
five schedules are null, both values match, and all nine applications still have no deployments.
Next is source/build-settings preparation. See the
[current execution plan](docs/deployment/staging-cra-122.md).

## Active local implementation — CRA-125 — 2026-09-07

**Published update:** Denys authorized the ten-commit CRA-125 push. Direct remote readback and
local main both resolve to `2275cee1ae46da708f33a032229e708c73a966c8`; the update from `e18af71`
was a normal fast-forward. The index is empty and unrelated changes remain local. Earlier
no-push and old-candidate statements below are dated checkpoints. The full 809-pass gate remains
unchanged. CRA-122 Stage 2 now proposes this published SHA, pending its exact acceptance.
Fresh read-only Railway status confirmed PostgreSQL SUCCESS with one active deployment, and
nine application services with no source/latest deployment and zero active deployments.

**Latest local Git state:** Denys authorized all ten selective commits. The nine app/test
checkpoints are committed as `d24e7a2..b9a66e8`; the final documentation checkpoint records
their evidence. Every mapped focused suite and Ruff/mypy check passed, with 0 failed/skipped
tests. Python sources still match the full 809-pass run. The earlier uncommitted/commit-pending
statements in this dated execution history are superseded. No push or staging deployment occurred.

**Latest result: local implementation and verification complete, ready for acceptance.**
One fresh full PostgreSQL 16 run: **809 passed, 0 failed, 0 skipped; 1984.30s**.
Independent gates: statements **11408/12135 = 94.01% PASS**; branches
**2041/2538 = 80.42% PASS**; unchanged nine-file critical aggregate
**1293/1443 = 89.60% PASS**. Ruff format/check and strict mypy pass. Full source inventory
is verified and the app/test source hash stayed unchanged during the run. The lower counts
and failed branch gates below are dated historical checkpoints, superseded for current
local evidence by this result. The authorized local commit range is recorded above.

Denys authorized the seven-checkpoint coverage plan and creation of [CRA-125](https://linear.app/craftspacee/issue/CRA-125/close-independent-backend-statement-and-branch-coverage-gates). This supersedes the pending implementation-approval wording in the dated planning record below. Commits and external actions remain unauthorized.

Checkpoint 1 is implemented locally: gate helper plus 16 passing unit tests. Denys then
authorized the precise menu PATCH correction: invalid merged input now returns the existing
safe 422 error, with rollback and a successful subsequent PATCH verified. The adjacent menu
suite passed 69 tests; six further import/publication cases also passed within a 15-test run.
Coverage tests now also exercise training schema/asset/draft/publication rejection and
assessment prerequisites. These are focused results, not a new full coverage gate.

Denys approved the subsequent cursor correction and Linear synchronization. Both Admin Attention
and Retake Requirements lists now reject timezone-less cursor timestamps with 422 INVALID_CURSOR
before comparison, including empty lists. Four RED cases became GREEN; all four mapped follow-up
files passed 23 tests with zero failures/skips. Valid next-page traversal remains verified.
Checkpoint 6 operations/security tests and the first fresh full run are complete locally.
That full PostgreSQL 16 run passed 711 tests, zero failed/skipped, in 1606.36s:
statements 11104/12135 = 91.50% PASS; branches 1860/2538 = 73.29% FAIL;
fixed critical aggregate 1241/1443 = 86.00% PASS. CRA-125 is not accepted.

Subsequent refinement passed 65 focused tests with zero failed/skipped in 197.34s and
executed 97 destinations missing from that full report. This diagnostic comparison leaves
74 destinations to the branch threshold; it is not merged full-run acceptance. A later
publication/assignment package passed 16 tests in 71.52s; its gain is not included above.

Denys authorized the subsequent retake-action correction. An unrelated Interactive or Practice
Attempt no longer selects `resume_retake` for a Final Exam Requirement: the query now filters
by the stable target Assessment. Fresh RED: 2 failed, 1 passed; four-file GREEN: 28 passed,
zero failed/skipped. Frozen and cancelled actions remain correct. A later refinement run
passed 95 tests, followed by 20 prerequisite/history/MFA checks, 8 takeover checks and the
Final Exam resume/readback/finish scenario. These are separate focused runs.
The final full run passed all 809 tests and all three coverage gates with isolated data.
See the [execution record](docs/testing/coverage-closure-plan.md) for the accepted boundary.
Ruff format/check (238 files) and strict mypy (217 source files) pass. No commit, push or deployment occurred.
CRA-122 staging Stage 2 remains separate and open; Linear synchronization is authorized.

Published main is `e18af71f89d587b1cb6b472cf189e67dfa8102a0` (CRA-123 Caddy and CRA-124 S3 corrections included).
Local main and GitHub match. CRA-121 is Done; CRA-122 Stage 1 is complete and Stage 2 remains
open. The proposed staging candidate is `e18af71`, subject to exact acceptance, not an approved
rollout. PostgreSQL was Online and all nine application services Offline in the September 7 audit.
Browser SQL and the two NOLOGIN DB roles were verified September 5; LOGIN/secrets/runtime grants
and live acceptance remain pending. Budget and owner-only test sender/recipient are already
agreed; cost controls and provider scope still need closure.

The [September 7 audit](docs/testing/repository-audit-2026-09-07.md) records 552 backend tests,
72 Vitest tests, 42 Playwright executions and 5 artifact/topology tests passing with zero
failures/skips in those suites. Statements: 89.22%; branches: 67.76%; combined: 85.51%.
Denys approved independent overall gates of at least 80% statements and at least 80% branches
on September 7. That original audit passed statements and failed branches; CRA-125 now passes
both gates as recorded above. See the [coverage closure plan](docs/testing/coverage-closure-plan.md).
Original Dashboard/logout-all scope, formal corrective acceptance and exact Stage 2 approval
remain explicit decisions. Do not claim live staging acceptance from
these results. CRA-19 visual work is separate from the existing functional frontend.

Canonical entry: [Linear START HERE](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974).
Current documentation synchronization is authorized under CRA-122; it is not commit, push or
provider-execution approval. The existing user changes and protected assets are preserved.

The accepted checkpoints below are dated historical evidence; the current audit metrics above
must not be replaced by their older combined-coverage wording.

## Accepted implementation and planning checkpoints

- CRA-20 Stage 0 is accepted and Done.
- CRA-21 repository baseline and agent context is accepted and Done.
- CRA-22 atomic commit workflow is accepted and Done.
- CRA-23 retrospective selective first-baseline commit map is accepted and Done.
- CRA-24 repository-context synchronization is accepted and Done.
- CRA-25 selective five-commit baseline execution is accepted and Done.
- CRA-26 initial baseline publication and state synchronization is accepted and Done.
- CRA-27 Stage 1 identity-persistence implementation plan is accepted and Done.
- CRA-28 Stage 1 identity-persistence implementation is accepted and Done.
- CRA-29 Stage 2 auth/session/CSRF/MFA/RBAC plan is accepted and Done.
- CRA-30 Stage 2 auth/session/CSRF/MFA/RBAC implementation is accepted, Done, and published.
- CRA-31 Stage 3 invitation plan is accepted and Done.
- CRA-32 Stage 3 invitation administration implementation is accepted, Done, and published.
- CRA-33 Stage 4 invitation-acceptance plan is accepted and Done.
- CRA-34 Stage 4 invitation-acceptance implementation is accepted, Done, and published.
- CRA-35 Stage 5 Pending/Admin Profile Setup plan is accepted and Done.
- CRA-36 Stage 5 Pending/Admin Profile Setup implementation is accepted, Done, and published through
  `de6dd84`. Its five selective local commits and fast-forward push were explicitly authorized on
  2026-08-27.
- CRA-37 Stage 6 Explicit Activation plan and five-checkpoint map are accepted and Done.
- CRA-38 Stage 6 Explicit Activation implementation is accepted, Done, and published.
- CRA-39 Stage 7 Full Regression and Acceptance Gate plan is accepted and Done.
- CRA-40 Stage 7 implementation is accepted, Done, and published through `abad74e`.
- CRA-41 Frontend MVP Vertical Slice 1 plan and six-checkpoint map are accepted and Done.
- CRA-43 Frontend MVP Vertical Slice 1 implementation is accepted, Done, and published through
  `fa30a1f`.
- CRA-46 post-acceptance repository documentation synchronization is accepted, Done, and published
  through `586f8c5`.
- CRA-47 Menu Source of Truth planning and its ten-checkpoint implementation map are accepted and
  Done.
- CRA-48 published-baseline documentation synchronization is accepted, Done, and published. Its
  primary checkpoint is `3b95b3c`; the corrective publication record removes temporary pre-push
  wording, and no CRA-48 push remains pending.
- CRA-49 Menu Source of Truth implementation and corrective acceptance tail are accepted and
  published through `8028d6e`.
- CRA-53 Training Content planning and its nine-checkpoint implementation map are accepted and
  Done.
- CRA-54 Training Content is accepted, Done, and published through `d955f6a` as nine atomic
  checkpoints.
- CRA-55 post-CRA-54 documentation synchronization is Done.
- CRA-56 Slice 4 planning and its nine-checkpoint map are accepted and Done.
- CRA-57 Slice 4 implementation is accepted, Done, and published through `d4e0184`.
- CRA-58 is the documentation checkpoint that records CRA-57 acceptance and publication.
- CRA-60 Slice 5 planning and its nine-checkpoint implementation map are accepted and Done.
- CRA-61 Slice 5 Interactive Training is accepted and Done as `93ce970..614da3d`; CRA-62 owns its
  repository synchronization and publication evidence.
- CRA-62 is accepted, Done and published through `c79db9d`.
- CRA-63 Slice 6 Practice planning and its forty-scenario/eight-checkpoint map are accepted and Done.
- CRA-64 Slice 6 Practice is accepted and Done as `74c5741..cc1c05a`; CRA-65 owns documentation
  synchronization and ordinary publication.
- CRA-65 is accepted, Done and published through `4164b9c`.
- CRA-66 Slice 7 Final Exam planning and its eight-checkpoint implementation map are accepted and
  Done.
- CRA-67 Slice 7 Final Exam and canonical Results is accepted and Done as
  `6be8f4d..703872b`; CRA-68 records its documentation synchronization and ordinary publication.
- CRA-68 is accepted, Done and fast-forward published through `9ef9fe1`.
- CRA-69 Slice 8 planning and its 65-scenario/eight-checkpoint map are accepted and Done.
- CRA-70 is Done and published as documentation checkpoint `5352f89`.
- CRA-71 Slice 8 implementation is accepted, Done and published as `62a80a0..054d731`.
- CRA-72 is Done and its post-acceptance documentation checkpoint is published at `4019262`.
- CRA-74 is Done and records the ordinary fast-forward publication through `4019262`.
- CRA-75 owns this publication-state documentation checkpoint.
- CRA-77 local implementation and hardening uses the authorized thirteen-checkpoint map. The full
  local range is `974feeb..ef74be4`; fresh independent review and the complete local gate pass.
  CRA-77 is accepted, Done, and published as part of the baseline through `c8a1135`.
- CRA-119 uses the authorized seven-checkpoint map. Its accepted range starts at
  `b1d145b` and includes API/worker runtime composition, async idempotent Resend adapters, Caddy
  frontend delivery, and an unapplied Railway topology. It is Done and published through `2644b796`.
- CRA-121 staging provisioning is accepted and Done, with Resend setup explicitly deferred.
- CRA-122 is active at Stage 2. The September 7 status check confirms PostgreSQL Online and nine
  application services Offline. Detailed source/secret/SQL inventory remains dated September 5:
  browser psql succeeded and both NOLOGIN roles were created; the SSH timeout is historical.
- CRA-123 and CRA-124 are implemented, verified and published through `e18af71`.
  Their formal acceptance disposition and the staging candidate decision remain explicit.
- Accepted runtime: Python 3.12.10 and PostgreSQL 16.15.
- Accepted local database boundaries: Docker Compose PostgreSQL 16 or native PostgreSQL 16,
  always with `APP_ENV=test` and an explicitly test-scoped database.
- Final CRA-20 evidence: `22 passed / 0 failed / 0 skipped`, 95% Stage 0 coverage, Alembic head
  `0001_stage0`, and a live async SQLAlchemy/asyncpg round-trip on PostgreSQL 16.15.
- The canonical five-commit baseline map and its exact selective path arrays are recorded in
  [CRA-23](https://linear.app/craftspacee/issue/CRA-23/prepare-retrospective-selective-first-baseline-commit-map).

The Stage 0 gate was rerun successfully during the selective baseline execution recorded in
CRA-25; the canonical acceptance history remains in CRA-20.

## Accepted Stage 1 checkpoint

- CRA-28 implements the accepted Stage 1 identity persistence boundary.
- Accepted gate: Python 3.12.10, PostgreSQL 16.15, `47 passed / 0 failed / 0 skipped`, 97%
  statement/branch coverage, Alembic head `0002_identity_persistence`, and no metadata drift.
- The candidate adds only Organization, Location, OperationalRole, User,
  OrganizationMembership, EmployeeProfile, and AuditEvent persistence.
- CRA-30 implements the accepted Stage 2 authentication/session/CSRF/MFA/RBAC boundary.
- Accepted CRA-30 gate: Python 3.12.10, PostgreSQL 16.15,
  `92 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 92% critical auth
  coverage, Alembic head
  `0003_auth_security`, and no metadata drift.

## Accepted and published Stage 3 checkpoint

- CRA-32 implements the accepted invitation lifecycle boundary: persistence, transactional email
  outbox, deterministic versioned tokens, persistent idempotency and rate limits, create,
  validate, resend, and revoke.
- Accepted local gate: Python 3.12.10, PostgreSQL 16.15,
  `156 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 90% critical
  invitation coverage, Alembic head `0005_invitation_email_outbox`, and no metadata drift.
- Provider calls, a worker/runtime deployment, invitation acceptance, list/detail endpoints, and
  non-test provisioning remain outside CRA-32.
- Denys accepted CRA-32 on 2026-08-27. Linear records it as Done, and its six commits are published.

## Accepted and published Stage 4 checkpoint

- CRA-34 adds only `POST /api/v1/invitations/accept`: locked Invitation authority, new/existing
  User branches, Pending Membership and placeholder EmployeeProfile creation, an opaque Session,
  a safe audit trail, and the Secure HttpOnly cookie response.
- Acceptance is atomic and tenant-isolated. Same-token and same-email races have one winner;
  failure paths roll back domain, session, and audit mutations. Acceptance never activates a
  membership or records MFA verification.
- Current local gate: Python 3.12.10, PostgreSQL 16.15,
  `180 passed / 0 failed / 0 skipped`, 94% overall statement/branch coverage, 93% aggregate
  critical acceptance coverage, Alembic head `0005_invitation_email_outbox`, and no metadata
  drift.
- The first full gate exposed a stale deterministic test clock, not a product failure. The clock
  was moved forward without changing production behavior; the focused API suite then reported
  `12 passed` and the full gate was green.
- Denys accepted CRA-34 on 2026-08-27. Linear records it as Done, and its four commits are published.

## Accepted and published Stage 5 checkpoint

- CRA-36 adds MFA-verified Admin Organization/Location/OperationalRole reads, cursor-paginated
  Employee list/detail, authenticated own read-only operational profiles, and CSRF-protected
  Pending-only profile setup.
- Employee identity is `EmployeeProfile.id`; every Admin query remains Organization-scoped.
  Foreign Employee/reference probes are non-enumerating, archived references remain explainable
  but are not selectable, and profile completeness is derived.
- Successful profile update appends a safe `employee_profile_updated` audit in the same transaction.
  Name/email values are not copied into audit. Forced commit failure rolls back domain and audit.
- Membership remains Pending in CRA-36. That issue deliberately excludes Stage 6 Activation,
  applicability, Assignments, notifications, Active/Disabled lifecycle changes, providers,
  frontend, and deployment.
- Accepted gate: Python 3.12.10, PostgreSQL 16, `195 passed / 0 failed / 0 skipped`, 94% overall
  branch coverage, and 92% aggregate critical Stage 5 coverage.
- Alembic remains at `0005_invitation_email_outbox`; empty-database migration coverage passes,
  `current --check-heads` passes, and autogenerate reports no metadata drift.
- The five CRA-36 checkpoints are committed on `main` and fast-forward published through
  `de6dd84`. Canonical acceptance and push evidence remains in Linear/Git.

## Accepted CRA-38 Stage 6 checkpoint

- Adds `POST /api/v1/organizations/{organization_id}/employees/{employee_id}/activate` for an
  authenticated, MFA-verified same-Organization Admin with CSRF and a required trimmed
  `Idempotency-Key`.
- Locks the scoped EmployeeProfile and Membership, revalidates nonblank names and active
  same-Organization Role/Location references, then moves only Pending Membership to Active.
- The same transaction records `activated_at`, clears `disabled_at`, appends one PII-safe
  `employee_activated` audit, and reserves the existing API idempotency record. Failures roll back
  all three boundaries.
- Same-key replay creates no duplicate audit. Concurrent same-key requests converge on one result;
  concurrent different keys produce one success and one `EMPLOYEE_ACTIVATION_NOT_ALLOWED` conflict.
- Training participation is derived as Active. The explicit applicability call returns zero
  published content, assignments, and notifications; no placeholder data, job, provider call,
  schema object, or migration is added. Activation issues no new Session.
- Focused Stage 6 API/integration/security evidence: `21 passed / 0 failed / 0 skipped`; the final
  API-only activation/security subset reports `18 passed / 0 failed / 0 skipped`.
- Full candidate gate: Python 3.12.10, PostgreSQL 16, `211 passed / 0 failed / 0 skipped`, 94%
  overall branch coverage, and 92% coverage for `app/services/employees.py`. Ruff format/check and
  mypy pass.
- Alembic remains at `0005_invitation_email_outbox`; empty-database migration coverage,
  `current --check-heads`, and autogenerate no-drift checks pass.
- The accepted CRA-38 series is `0291208`, `e53e614`, `b0cd89b`, `c55545a`, and `bd2f98e`; it is
  published as part of the backend baseline through `abad74e`.

## Accepted CRA-40 Stage 7 checkpoint

- Adds one test-only complete backend acceptance chain: real Admin password login and MFA,
  Invitation create, persisted outbox and fake delivery capture, new-User acceptance, Pending
  restriction, Admin profile setup, explicit idempotent Activation, and Active access through the
  same employee Session.
- Adds a separate deny-by-default assertion for a Disabled Membership at the existing Active
  employee authorization guard.
- No production code, API contract, schema, migration, dependency, provider, worker, frontend, or
  `Photos/` change was required.
- Focused Stage 7 evidence: `2 passed / 0 failed / 0 skipped`. Adjacent auth, invitation, employee,
  security, delivery, and applicability evidence: `85 passed / 0 failed / 0 skipped`.
- Full candidate gate: Python 3.12.10, PostgreSQL 16, `213 passed / 0 failed / 0 skipped`, 94.05%
  exact overall statement/branch coverage, and 91.80% aggregate coverage across the declared
  17-file critical first-slice set. Ruff format/check and strict mypy pass.
- Alembic remains at `0005_invitation_email_outbox`; empty-database migration coverage,
  `current --check-heads`, and metadata no-drift checks pass.
- OpenAPI exposes 17 paths; all eight required first-slice paths are present and the forbidden
  `password_hash`, `token_hash`, `csrf_token_hash`, `secret_encrypted`, and `raw_token` fields are
  absent.
- The CRA-40 checkpoints are `a7c73df`, `2fd8254`, and `abad74e`; the accepted backend baseline is
  published on `origin/main` through `abad74e`.

## Accepted and published CRA-43 frontend checkpoint

- Adds the approved React 19/TypeScript/Vite/Tailwind toolchain with exact pinned dependencies and
  no global-state, form-schema, mock-server, animation, icon, or OpenAPI-generator dependency.
- Uses the accepted cookie session, CSRF, idempotency, MFA, invitation, Employee, and Activation
  contracts without changing the backend or persisting secrets in browser storage.
- Implements responsive Admin and Employee shells, login/MFA, invitation acceptance, Pending
  state, Admin invitation/profile setup, separate confirmed Activation, and truthful Active home.
- Vitest/Testing Library: 13 passed, 0 failed, 0 skipped across nine files.
- Playwright: 3 passed, 0 failed, 0 skipped at 1440×1000, 768×1024, and 375×812.
- The accepted series is `5b7e637`, `0ea5f14`, `6bcc8c4`, `b1aa74b`, `c5f38a8`, and `fa30a1f`.
  It was fast-forward published without history rewriting.

## Repository and runtime state

- Branch: `main`; accepted published history contains the CRA-74 product/documentation endpoint
  `4019262`, followed by the CRA-75 publication-state documentation checkpoints.
- Repository history includes the accepted backend and frontend MVP Vertical Slice 1 checkpoints
  published through the CRA-43 endpoint `fa30a1f`, the accepted CRA-46/CRA-48 documentation
  checkpoints, CRA-49 through `8028d6e`, CRA-54 through `d955f6a`, CRA-55 through `afc607a`, and
  CRA-57 through `d4e0184`; later accepted publication checkpoints are CRA-62 at `c79db9d`, CRA-65
  at `4164b9c`, CRA-68 at `9ef9fe1`, and CRA-74 through `4019262`.
- Git remote: `origin` points to the approved `GarnikSacsha/HorecaFam-` repository.
- Published branch: CRA-49 and its corrective acceptance tail end at `8028d6e`; CRA-54's
  `8e15bd2..d955f6a`, CRA-55's `afc607a`, and CRA-57's `5823a0e..d4e0184` follow without force-push
  or history rewriting. CRA-61/62, CRA-64/65, CRA-67/68 and the CRA-70/71/72 range published by
  CRA-74 follow through `4019262` with the same fast-forward-only invariant.
- Native PostgreSQL service: `postgresql-x64-16`, installed locally for the accepted test boundary.
- Local `backend/.env.test`: present and ignored; its values must never be printed or committed.
- Docker Desktop is installed; CRA-123 recorded successful local builds and HTTP checks on
  2026-09-04. The Linux engine was unavailable during the 2026-09-05 audit.
- `frontend/`: accepted CRA-71 Admin Attention/Retakes and Employee follow-up implementation.

## Accepted and published CRA-57 checkpoint

- Scope: version-owned audiences, shared applicability, immutable Assignment history, explicit
  Lesson Completion, derived current Progress, deterministic replacement-Version Rollout,
  transactional provider-free notification jobs, Admin assignment/rollout controls, and
  assignment-aware Employee Home/Learning.
- Backend gate: 363 passed, 0 failed, 0 skipped; 88% overall statement/branch coverage and 87%
  aggregate coverage across the seven Slice 4 service files; Ruff format/check and strict mypy
  passed.
- Migrations: accepted head `0009_assignment_completion_rollout`; empty-database upgrade,
  downgrade/upgrade coverage, current-head validation, and metadata no-drift passed.
- Frontend gate: Prettier, ESLint, TypeScript, and production build passed; Vitest reports 35
  passed, 0 failed, 0 skipped across 14 files.
- Browser gate: Playwright reports 12 passed, 0 failed, 0 skipped across 1440×1000, 768×1024,
  and 375×812 projects, including explicit Completion and Admin Assignment/Rollout confirmation.
- Exact evidence and limitations:
  [`docs/testing/training-assignment-slice-4-acceptance.md`](docs/testing/training-assignment-slice-4-acceptance.md).
- Denys explicitly accepted CRA-57; its nine-checkpoint range `5823a0e..d4e0184` was
  fast-forward published. No PR, merge, provider, deployment, or production configuration was
  performed.

## Accepted and published CRA-54 checkpoint

- Backend: 318 passed, 0 failed, 0 skipped on Python 3.12.10 and native PostgreSQL 16; 88% overall
  statement/branch coverage and 80% aggregate coverage across the predeclared seven-file critical
  Training set. Ruff format/check and strict mypy passed.
- Migrations: head `0008_training_content`; empty-database upgrade, Training migration round-trip,
  current-head validation, and metadata no-drift passed.
- Frontend: Prettier, ESLint, TypeScript, and production build passed; Vitest reports 27 passed,
  0 failed, 0 skipped across 14 files.
- Browser: Playwright reports 9 passed, 0 failed, 0 skipped across 1440×1000, 768×1024, and
  375×812 projects. The CRA-54 path covers Admin readiness/publication through Active Employee
  Module/Lesson reading.
- Scope: versioned Draft/Published Training content, seven strict block types, private images,
  atomic publication, and published-only Employee reference are implemented. Assignments,
  completions, progress, rollout, notifications, Practice, exams, and providers remain absent.
- Exact evidence and limitations:
  [`docs/testing/training-slice-3-acceptance.md`](docs/testing/training-slice-3-acceptance.md).
- Denys accepted CRA-54 and authorized fast-forward publication of the nine-checkpoint range
  `8e15bd2..d955f6a`. No Railway/provider smoke, PR, merge, deploy, or production configuration was
  performed.

## Accepted CRA-49 checkpoint and corrective closure

- Backend: 270 passed, 0 failed, 0 skipped on Python 3.12.10 and native PostgreSQL 16; 89% overall
  statement/branch coverage; Ruff format/check and strict mypy passed.
- Corrective RED → GREEN evidence: concurrent same-key Import Confirm reproduced `[200, 409]`
  in three of three runs, then returned replay-safe `[200, 200]` in three of three runs after a
  post-lock idempotency recheck. Different-key conflicts remain one-winner/one-conflict.
- Denys accepted the corrective coverage gate on 2026-08-28: at least 80% overall backend coverage
  with branch tracking, every mandatory Slice 2 scenario mapped, and explicit concurrency/security
  proof. No undeclared critical file set is selected retroactively.
- Migrations: head `0007_menu_import_review`; current-head, empty-database/round-trip coverage, and
  metadata no-drift passed.
- Frontend: Prettier, ESLint, TypeScript, and production build passed; Vitest reports 19 passed,
  0 failed, 0 skipped across 12 files.
- Browser: Playwright reports 6 passed, 0 failed, 0 skipped across desktop, compact, and mobile;
  the Menu path covers Admin JSON review/publication through Active Employee search/detail.
- Scope/security: Employee reads expose only the own Active Profile's current Published Menu;
  Training content, Assignments, and notifications remain zero-applicability; `Photos/` is
  untouched and unstaged.
- Exact matrix and limitations: [`docs/testing/menu-slice-2-acceptance.md`](docs/testing/menu-slice-2-acceptance.md).

## Accepted CRA-61 Interactive Training

- Scope: provenance-bound deterministic Question Candidates, Admin review/publication/readiness,
  immutable five-question Interactive Training Attempts, progressive idempotent Answers,
  immediate feedback, device takeover, Results, Latest/Best history, and responsive Admin/
  Employee UI.
- Backend gate: 424 passed, 0 failed, 0 skipped; 88% overall statement/branch coverage and 86%
  aggregate coverage across the predeclared five Slice 5 service files; Ruff and strict mypy pass.
- Migrations: head `0013_question_templates`; 13 migration tests, clean upgrade/current head and
  metadata no-drift pass. Active category, component, allergen and description rules are seeded by
  migrations.
- Frontend gate: Prettier, ESLint, TypeScript and production build pass; Vitest reports 45 tests;
  Playwright reports 15 executions across 1440×1000, 768×1024 and 375×812.
- Exact 27-scenario mapping and limitation:
  [`docs/testing/interactive-training-slice-5-acceptance.md`](docs/testing/interactive-training-slice-5-acceptance.md).
- Automated Candidate generation covers deterministic category/single-choice,
  components/multiple-choice, allergens/recognition and description/recognition templates from
  verified, unambiguous source facts. Ordering/assembly and matching templates are not generated
  because the current menu model does not prove preparation order or verified pair semantics.
- Denys explicitly accepted this evidence and its remaining source-bound limitation. The accepted
  range ends at `614da3d`; CRA-62 owns publication and exact remote evidence.

## Accepted CRA-64 Practice checkpoint

- Scope: Training-scoped `whole_menu_knowledge_check`, ten distinct Menu Items, final-only
  feedback, seven effective inactivity days with pause freeze/takeover, explicit atomic finish,
  Knowledge, critical-allergen evidence, durable Final Exam eligibility, Latest/Best/history,
  Admin readiness and Employee UI.
- Persistence head: `0014_practice_persistence`, including generic 5/10/20 assessment constraints
  and tenant-owned immutable eligibility.
- Source boundary: verified components, allergens and deterministic missing-component facts only;
  assembly/serving remains excluded without a structured approved source.
- Exact forty-scenario evidence and limitations:
  [`docs/testing/practice-slice-6-acceptance.md`](docs/testing/practice-slice-6-acceptance.md).
- Final Exam execution/certification and canonical management Results are accepted in CRA-67.
  Attention/Retakes are accepted and published in CRA-71 as described below; providers, deployment and
  real Bacara ingestion remain absent.

## Accepted CRA-67 Final Exam checkpoint

- Scope: readiness and a balanced immutable 20-question pool, eligibility, seven effective
  inactivity days, device takeover, feedback-free Answer saves, explicit confirmed finish,
  exact 70% passing, critical-error evidence, certification, history and canonical Admin Results.
- Employee UI covers readiness, resume/start, all 20 questions, final confirmation, review and
  failed-attempt immediate retake. A passed certification has no retake action in this slice.
- Admin UI exposes Final Exam readiness plus Organization-scoped Results overview/detail without
  adding a leaderboard or a separate certification table.
- PostgreSQL full regression: 445 passed, 0 failed, 0 skipped, 85% overall coverage. The new
  focused real-database acceptance test separately reports 1 passed and proves same-key
  concurrent finish convergence.
- Frontend: Prettier, ESLint, TypeScript and production build pass; full Vitest reports 57 passed;
  full Playwright reports 21 passed. Final post-copy focused reruns report 2 Vitest and 3
  Playwright executions passed.
- Alembic remains at `0014_practice_persistence`; upgrade, current-head and metadata no-drift
  checks pass. CRA-67 adds no migration, dependency, provider, deployment or production action.
- Exact evidence and limitations:
  [`docs/testing/final-exam-slice-7-acceptance.md`](docs/testing/final-exam-slice-7-acceptance.md).

## Accepted CRA-71 Attention and Retakes checkpoint

- Scope: six-table persistence/backfill, immutable Critical Error projection, seven-day Retake
  lifecycle/timing, explicit Attention workflow, protected Admin/Employee APIs, authorized
  certified retakes, responsive Admin/Employee UI and two three-viewport browser journeys.
- Gate: 463 backend tests passed with 86% statement/branch coverage; Ruff and strict mypy passed.
  Alembic upgrade/current/no-drift is green at `0015_attention_retakes`.
- Frontend: Prettier, TypeScript, ESLint and production build passed; Vitest reports 58 passed
  across 19 files; Playwright reports 27 passed across the three approved viewport projects.
- Exact accepted evidence and remaining external gates:
  [`docs/testing/attention-retakes-slice-8-acceptance.md`](docs/testing/attention-retakes-slice-8-acceptance.md).
- Exact range: `62a80a0..054d731`; all eight checkpoints are committed, published and CRA-71 is Done.
- CRA-72 records the post-acceptance documentation synchronization; CRA-74 published the complete
  CRA-70/71/72 range through `4019262`.

## CRA-77 accepted local evidence

- Full dedicated-PostgreSQL gate: 530 passed, 0 failed, 0 skipped; 86% overall statement/branch
  coverage and 81% aggregate coverage across the predeclared CRA-77 critical set.
- Ruff format/check, strict mypy, Alembic upgrade/current/no-drift at `0018_job_runtime`, frontend
  formatting/lint/types/build, 72 Vitest tests and 42 Playwright executions all passed.
- Synthetic invitation through passing Final result and dry-run/idempotent synthetic bootstrap are
  covered. No non-test bootstrap apply or real Bacara data mutation occurred.
- Detailed evidence, security review, compatibility corrections and explicit release limitations
  are in
  [`docs/testing/operations-hardening-slice-9-acceptance.md`](docs/testing/operations-hardening-slice-9-acceptance.md).

## CRA-119 accepted deployment readiness evidence

- Full dedicated-PostgreSQL gate: 544 passed, 0 failed, 0 skipped with 86% overall
  statement/branch coverage.
- Ruff format/check, strict mypy, Alembic current/no-drift at `0018_job_runtime`, frontend
  formatting/lint/types/build and 72 Vitest tests passed.
- Frontend deployment-artifact checks report 2 passed; Railway topology typecheck and 3 static
  tests passed.
- Docker container builds were not run because the local Docker engine was unavailable. Railway
  plan/apply, provisioning/deploy/rollback, real Resend delivery, provider configuration, and all
  production mutations remain unperformed.
- Detailed boundary, evidence, security review, contract impact, and next gate:
  [`docs/testing/deployment-provider-readiness-cra-119.md`](docs/testing/deployment-provider-readiness-cra-119.md).

## Remaining to a functional and pilot-ready MVP

CRA-122 is the active bounded deployment issue. Its [Stage 2 plan](docs/deployment/staging-cra-122.md)
records source/build/variable/rollback decisions and unresolved gates. Pilot release still requires
separately authorized external evidence:

1. Real Bacara content validation and venue UAT.
2. Provider configuration, backup retention plus isolated restore proof, and deploy/rollback smoke.
3. An accepted staging load profile and performance evidence.
4. Manual accessibility review where automation cannot prove screen-reader/contrast behavior.

The published functional Slice 8 boundary remains accepted. CRA-77 closes the local code and
synthetic hardening boundary, but the external gates above remain unperformed and cannot be
reported as passing.

## Protected uncommitted material

- `Photos/` contains seven project-asset JPG files for
  [CRA-19 Bacara Welcome / homepage](https://linear.app/craftspacee/issue/CRA-19/design-bacara-welcome-brand-intro-responsive-mockups).
- These assets are deferred from the initial backend/docs baseline and remain untouched,
  unignored, and unstaged.
- Do not move, rename, optimize, delete, ignore, stage, commit, or publish them unless a separate
  bounded CRA-19 implementation/asset commit map explicitly authorizes those actions.
- Local environments, caches, coverage data, installers, and acceptance helpers are not baseline
  artifacts even when present on disk.

## Authority and next gates

- The currently active bounded task is always determined through Linear START HERE and the single
  active Linear issue, not through this snapshot.
- CRA-121 is accepted and Done. CRA-122 Stage 1 is complete; Stage 2 planning and status
  synchronization were requested by Denys on 2026-09-04. This is not source-binding, secret,
  migration, deployment, provider-send, or local-commit authorization.
- CRA-119 is accepted, Done, and published through `2644b796`; it is not deployed.
- CRA-77 is accepted, Done, and published as part of the baseline through `c8a1135`. CRA-19 remains
  a separate visual-only track.
- CRA-71 is accepted, Done and published as `62a80a0..054d731`; CRA-72 records its exact
  nine-document synchronization, and CRA-74 records publication through `4019262`.
- CRA-69 planning is accepted and Done; CRA-70 is published at `5352f89`.
- Push, PR, merge, provider and deployment actions remain separately gated.
- The accepted five-commit CRA-23 map was executed locally under the explicit CRA-25
  authorization and accepted by Denys. Its initial publication and repository-state synchronization
  are recorded in CRA-26. Further staging or commits require a new bounded map and explicit
  authorization.
- Every later push remains a separate approval gate, as do PR, merge, history rewrite, Railway,
  and deployment.
- CRA-28 local commit and initial publication were separately authorized by Denys; their exact Git
  evidence remains canonical in CRA-28. Later commits and pushes require new explicit approval.
- CRA-32, CRA-34, and CRA-36 are accepted, Done, and published; their canonical implementation and
  Git evidence remains in Linear.
- CRA-37 through CRA-48 are accepted and Done. The CRA-43 implementation series ends at `fa30a1f`,
  and the published repository baseline includes the CRA-46 documentation checkpoint at `586f8c5`.
  CRA-48 and CRA-49 are accepted and published; the CRA-49 corrective endpoint is `8028d6e`.
  CRA-53 planning and CRA-54 implementation are accepted and Done; CRA-54 is published through
  `d955f6a`, and CRA-55 follows at `afc607a`. CRA-56 and CRA-57 are accepted and Done; CRA-57 is
  published through `d4e0184`, with CRA-58 providing this documentation checkpoint. Every later
  implementation, push, PR, merge, deploy, provider call, non-test mutation, production
  configuration, and history rewrite remains separately gated.

Update this file after each accepted bounded issue or material repository/runtime change. Keep
product and contract decisions in Linear rather than copying them here.

</details>

</details>
