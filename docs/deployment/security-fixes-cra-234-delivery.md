# CRA-234 bounded delivery preparation — 2026-09-21

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
