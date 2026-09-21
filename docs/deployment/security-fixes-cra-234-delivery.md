# CRA-234 bounded delivery preparation — 2026-09-21

## Admin follow-up completed — 2026-09-21, 14:00 UTC

Denys supplied a normal Organization Admin session. The two previously skipped read-only
checks now pass: **2 passed, 0 failed, 0 skipped** in this follow-up. Admin Results list,
detail and completed-answer review preserve certification, 95% (19/20), one completed exam,
70% Practice and one incorrect answer. Readiness shows 4/4 lessons ready, Practice ready
with 27 distinct Menu items, Final ready with 80 reviewed questions, rotation supported,
and zero candidates awaiting review. No generation, publication, content edit or new attempt
was performed. Together with the earlier seven UI checks, the planned rollout UI selection
is now **9 passed, 0 failed, 0 outstanding skips**; this is not a full staging acceptance gate.
The earlier missing-Admin-session limitation below is resolved. Owner acceptance, broader
staging/pilot gates and any live security/load testing remain separate. Only this report and
STATUS.md are updated. Denys subsequently authorized their selective commit and push.

## Completed API rollout — 2026-09-21

Denys authorized this prepared next step after publishing the four source checkpoints.
The API-only rollout is complete. Railway deployment
`e4ce2e9b-45b1-4692-a15a-e40b33790551` was created at 12:42:13 UTC and verified SUCCESS
at 12:45:08 UTC. The preflight baseline matched `adffd5f0-2675-4ca7-916a-9b3f1d8627de`.
The exact 399-file source directory corresponding to the sealed ZIP below was uploaded through
the existing Railway CLI source-upload route; it was not a raw checkout deployment.
Archive hash and every source/ZIP manifest entry passed before upload and again after delivery.

The existing API root `/backend`, Dockerfile build, `python -m app.api_server`,
`/api/v1/health`, one replica, ON_FAILURE/3, and deploy manifest are unchanged.
No explicit resource limit override was present in either deployment manifest; this check does
not establish account-level resource caps. There is no pre-deploy command or migration.
Web remains SUCCESS at `82941686-422a-4f05-a09d-c03ce43e26e5`, with identical metadata.

### Post-delivery checks

- Public HTTP: **8 passed, 0 failed, 0 skipped**. Health, API health, public entry and login
  return 200; unknown API and asset return 404; both existing JS/CSS assets return 200.
  HTML no-store and immutable asset cache headers pass.
- Authenticated read-only UI: **7 passed, 0 failed, 2 skipped**. Passed: certified Employee
  Home, persisted Final result/history (95%, 19/20), completed learning overview (4/4),
  four-lesson module, completed lesson with existing interactive history, published Menu item
  detail with unconfirmed allergens, and Operator Jobs retaining its existing records.
  Skipped: Admin readiness and Admin Results; available browser sessions are Employee and
  Platform Operator, not Organization Admin. No impersonation or credential change was attempted.
- API/web settings and deploy-manifest comparison: passed. Only the API deployment identity changed.
- Candidate parity: all 399 manifest and archive hashes match; six declared overlay paths only.

The earlier same-session 125 backend, 128 Vitest and six mock-browser checks apply to the
unchanged implementation. They were not rerun as hosted tests. No live saturation/body-exhaustion
probe, password-reset attempt, email send, new assessment attempt, content write, migration,
worker/cron delivery, variable/configuration change or dependency change was performed.
This proves delivery and selected normal runtime paths, not full hosted security/load acceptance.

### Evidence and recovery

Safe local evidence is retained under `outputs/cra-234-delivery-preflight-2026-09-21/`
(`provider-before.json`, `provider-after.json`) and `outputs/cra234-http-smoke.json`.
No secrets or raw provider logs are included in this report. Previous recoverable API remains
`adffd5f0-2675-4ca7-916a-9b3f1d8627de`; rollback was not needed or executed.

The four preceding commits are now published through `7d1f63d`. This rollout updates only
this report and `STATUS.md`; Denys subsequently authorized their selective commit and push.
Documentation-only TDD exception: provider/source parity, read-only smoke, link and diff checks.
Authorized checkpoint: `docs: record CRA-234 API rollout`, exactly these two paths, with
link/content/diff verification. The current direct authorization covers this two-path checkpoint and its push.
CRA-234 and CRA-122 remain In Progress pending their distinct acceptance gates.
The preparation-only statements below preserve the pre-approval checkpoint.

Status: local candidate prepared; not uploaded, deployed or accepted.
Preparation is part of the authorized CRA-122 audit follow-up. CRA-234 remains the bounded
behavior scope. No new implementation, dependency, migration or live data action is included.

## Exact artifact

- Baseline: the sealed 397-file CRA-271 API/web packet deployed September 17, preserving
  CRA-237/238/240. [Original delivery and recovery record](demo-ux-cra-271.md).
- Baseline archive SHA-256:
  `6aeb978e3f1678ac7b11b70f2060c323c4264f5fc651e4a3ef09bb750478759a`.
- Overlay source: published `9d68d9d6d231583f838a5921067ad435e418e08d`; the existing CRA-234
  checkpoints are `3b3c79a` and `0f767a6`. No recommit or history rewrite is needed.
- Local candidate: `outputs/cra-234-delivery-preflight-2026-09-21/source.zip` with adjacent
  `manifest.json`; 399 files. Helpers, environment files, dependencies, Git metadata, Photos
  and runtime output are not in the archive.
- Candidate SHA-256:
  `78b9de3cb5f9ec1d61332a7e4241df9221b08d02c0c2f51bc1c1e193fb49020b`.

Exactly six overlay paths:

1. `backend/app/services/password_recovery.py`
2. `backend/tests/api/test_password_recovery.py`
3. `backend/tests/api/test_rate_limit_capacity.py`
4. `backend/app/main.py`
5. `backend/app/core/request_body.py` (added)
6. `backend/tests/api/test_request_body_limit.py` (added)

All other baseline files are byte-for-byte preserved. All 396 non-Markdown candidate files
match the tested main working tree after normalizing only CRLF/LF. Tests run in that checkout,
not inside the sealed source directory. The three included Markdown files are historical packet
documentation; use STATUS and this report for current delivery authority. The sealed source is
not modified by testing. Final manifest/archive verification is required immediately before upload.

## Contract and service boundary

The existing accepted CRA-234 correction preserves generic 202 recovery responses, known-account
send throttling and valid reset-token use at anonymous capacity. Invalid tokens remain bounded;
one-use/expiry/revocation and locking remain enforced. Actual request bodies are limited to 16 MiB
before parsers/dependencies; allowed bytes replay unchanged. Normal menu import remains supported.
See [original RED/GREEN and compatibility decision](../testing/security-fixes-cra-234.md).

Only the existing staging API requires a rollout for these changes. Frontend, worker, cron,
dependencies, migration files, provider adapters and configuration are unchanged from the baseline
packet. No migration runner, schema grant, account setup, content publication or email send is
required. The worker's separate source history is not silently reconciled by this API-only step.

## Proposed later execution map — separate approval required

1. Read current Railway metadata for the exact existing staging environment/API. Confirm the
   latest successful API is still `adffd5f0-2675-4ca7-916a-9b3f1d8627de`, or stop and reconcile any
   new source before upload. Confirm web still retains the CRA-271 delivery; record drift without
   redeploying it. Recheck start command, root, health path and resource limits without changing them.
2. Rehash the candidate ZIP and every manifest path, check no extra files, verify unchanged
   migration 0020 and dependency manifests, and read the fresh focused gate/known formatting limit.
3. After explicit API-deployment approval, upload only this sealed source to the existing staging
   API using the established source-upload route. No source binding, autodeploy, variable, secret,
   schedule, replica or provider changes.
4. Wait for the new API's successful deployment and health. Run public health and routing reads,
   then authenticated read-only Menu/readiness/Results checks using a normal available session.
   Preserve the existing certification and content. Local test evidence proves saturation/body
   behavior; do not run a live saturation attack, reset attempt or email send as an implicit smoke.
5. Record deployment identity, UTC time, candidate hash, actual passed/failed/skipped checks,
   preserved web/source state and any limitation. Owner acceptance remains separate.

Stop if baseline/source identity drifts, the exact artifact cannot be proven, protected reads
fail, schema/config changes become necessary, an unexplained 5xx appears, or any operation needs
credentials or data outside the approved channel.

## Recovery boundary

Recorded recoverable API: `adffd5f0-2675-4ca7-916a-9b3f1d8627de` (CRA-271).
Recorded web: `82941686-422a-4f05-a09d-c03ce43e26e5`; unchanged by this API-only proposal.
CRA-234 adds no persistence schema and requires no data migration. Artifact rollback is therefore
schema-compatible, but still requires the explicit agreed deployment/recovery authority.
Never downgrade/drop migration 0020 or menu history as part of this rollback. Reverting the API
would also reintroduce the known CRA-234 availability limitations; record that tradeoff.

## Verification and remaining gates

Fresh local results and exact commands are in the [September 21 reconciliation](../testing/reconciliation-2026-09-21.md).
The original baseline hash was verified for all 397 files with no mismatches/extras before assembly.
This preparation does not prove live remediation, full coverage, Docker-image execution or
load/concurrency limits. No deployment, email, hosted write, Git index change, commit or push occurred.
