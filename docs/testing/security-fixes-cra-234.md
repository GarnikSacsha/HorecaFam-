# CRA-234 — security correction evidence

## Current reconciliation — 2026-09-16

Denys authorized selective local commits and Linear synchronization: recovery `3b3c79a`,
HTTP body boundary `0f767a6`. Both are local only; no deployment, provider send or non-test
mutation occurred. The earlier no-commit authorization and blocked Linear write below are
historical September 15 evidence, superseded for this authorized reconciliation.

Fresh recovery/capacity, reset delivery/database and worker selection: **36 passed, 0 failed,
0 skipped** (119.15 s). Fresh body/health/errors/menu-import selection: **41 passed, 0 failed,
0 skipped** (35.72 s). Ruff format/check pass (261 formatted files); strict mypy passes for
239 source files. Commands use the documented isolated test database procedure:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_password_recovery.py tests/api/test_rate_limit_capacity.py tests/integration/test_password_reset_delivery.py tests/integration/test_database.py tests/integration/test_background_job_handlers.py::test_password_reset_handler_reconstructs_active_token_and_finalizes_job -vv -p no:cacheprovider --tb=short
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_request_body_limit.py tests/api/test_health.py tests/api/test_errors.py tests/api/test_menu_import_api.py -vv -p no:cacheprovider --tb=short
```

A separate fresh read-only review pass in this reconciliation checked existing recovery locks,
valid-token authority, generic-response/send-throttle behavior, middleware order, actual-byte
counting, replay and the error envelope. No additional concrete defect was established. This
is the current agent's review, not another independent-agent scan. The independent September 15
review and RED evidence remain dated below. No new source behavior was authored here.

Full backend coverage, full browser regression, real proxy/load behavior and deployment were
not rerun. Counts from older selections overlap and must not be summed with fresh results.
[Current source and next boundaries](reconciliation-2026-09-16.md).

## Historical September 15 correction and verification


Date: 2026-09-15. Scope: local working-tree correction of two medium availability
findings from scan `d76429fd-1333-41c3-bb0c-316768983a28`.
Canonical issue: [CRA-234](https://linear.app/craftspacee/issue/CRA-234/fix-recovery-saturation-and-pre-parser-http-body-exhaustion).

Outcome: **fixed locally**. Both original triggers are covered by passing regressions;
deployment and owner acceptance are separate steps.

## Boundaries and contract impact

### Recovery under anonymous capacity exhaustion

Previously, 4096 active public authentication buckets prevented both a real user's
forgot-password request and redemption of a live reset token. New anonymous email
subjects also created durable rate-limit records.

Forgot-password now looks up the account under the existing email/user lock before
allocating send-throttle state. Unknown/passwordless users allocate none. Known users
retain five sends per rate window and internal suppression, with generic
`202 {"status":"accepted"}` for all syntactically valid requests, including throttled
ones. This deliberately supersedes CRA-170's externally visible recovery 429 tradeoff,
as approved in CRA-234. Existing schema validation and operational error handling remain.

Known-account buckets do not require public-capacity admission. Storage can contain the
4096 public allowance plus account-backed recovery rows; arbitrary absent emails cannot
increase it. Existing cleanup still retires old rows, including historical anonymous
forgot-password rows. Login and invalid-token capacity controls remain in place.

Reset checks token authority under the existing locks before consuming an anonymous
budget. A live token needs no new bucket. Invalid/expired/revoked/used tokens still use
the bounded public failure path. Password hashing, single use, sibling-token invalidation,
session revocation and MFA-challenge revocation remain transactional.

### HTTP body boundary

The shared ASGI middleware counts actual incoming bytes before passing a request to
FastAPI's parsers, dependencies or handlers. A declared oversized body is rejected before
reading; streamed bodies stop on overflow even with absent or understated length headers.
The buffer has a 16 MiB wire limit, with bounded storage independent of chunk count.
This allows normal JSON escaping of the existing 2 MiB canonical menu import limit.
Bodies exceeding the wire limit, including excessive whitespace, now return 413.

Rejections use the existing error envelope with `REQUEST_BODY_TOO_LARGE`, request ID and
CORS. Accepted bytes are replayed unchanged. Partial disconnected requests do not invoke
the handler. The boundary applies to the backend reached directly or through the proxy;
no Caddy configuration, dependency, schema or deployment change is required.

## Verification evidence

Commands below run from `backend/`, with the secret-safe test environment procedure in
`.harness/TESTING.md`. No provider sends or non-test database operations were performed.

### RED — before production changes

- Password recovery selection (`-k "public_capacity or persistent_state or throttles_known or queues_safe_outbox"`):
  4 failed, 1 passed, 12 deselected. Capacity returned 429 instead of 202; absent addresses
  created eight buckets instead of none; both account classes exposed the old sixth-call 429.
  Ordinary outbox behavior passed as the legitimate control.
- Separate two-case saturation run (`-k public_capacity`): 2 failed, 16 deselected.
  Forgot returned 429 instead of 202, and a token minted before saturation returned 429
  instead of 204. These failures were behavior failures on the configured test database.
- `rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_request_body_limit.py -vv -p no:cacheprovider --tb=short`:
  14 failed, 3 passed. Twelve streamed overflow cases reached the handler with 200;
  declared-overflow and disconnect guard assertions also failed. Empty, below-limit and
  exact-limit legitimate requests passed. The declared-overflow guard deliberately supplied
  no body and detected the unwanted receive call; it was not a setup failure.

### GREEN — focused checks and independent review

- Initial recovery/capacity run: 32 passed, 0 failed, 0 skipped.
- Initial HTTP/health run: 19 passed, 0 failed, 0 skipped.
- Independent fresh read-only boundary investigation before implementation; one fresh
  bypass/regression review of the candidate afterward. No concrete surviving bypass or
  regression reported. Reviewer independently ran the expanded body suite: 22 passed,
  0 failed, 0 skipped. Reviewer made no edits and ran no database tests.
- Frontend: `rtk pnpm test src/auth/SecurityRecoveryFlow.test.tsx` from `frontend/`:
  first attempt failed at Vite startup due to sandbox child-process restrictions (no tests
  executed). Same command with approved execution permission: 6 passed, 0 failed, 0 skipped.
- Final `rtk ..\.venv\Scripts\python.exe -m ruff format --check .`: 261 files formatted.
- Final `rtk ..\.venv\Scripts\python.exe -m ruff check .`: passed.
- Final `rtk ..\.venv\Scripts\python.exe -m mypy app tests`: passed, 239 source files.

Expanded backend regression run: **174 passed, 0 failed, 0 skipped** in 410.52 seconds.
Command:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_password_recovery.py tests/api/test_rate_limit_capacity.py tests/api/test_request_body_limit.py tests/api/test_health.py tests/api/test_errors.py tests/api/test_auth_login.py tests/api/test_auth_session.py tests/api/test_auth_csrf_logout.py tests/api/test_auth_mfa_rbac.py tests/api/test_auth_security_regressions.py tests/api/test_auth_logout_others.py tests/api/test_mfa_enrollment_recovery.py tests/api/test_menu_import_api.py tests/api/test_invitations_create_validate.py tests/integration/test_password_reset_delivery.py tests/integration/test_maintenance_jobs.py -vv -p no:cacheprovider --tb=short
```

This run covers the original saturation triggers, alternate body content types, exact byte
boundary/replay, token rotation/expiry/single-use, session and MFA revocation, competing
auth operations, tenant/CSRF controls, menu import, invitation admission and bounded cleanup.

During final review, the existing public-capacity cleanup test was switched from unknown
forgot-password to an invalid reset token: unknown forgot no longer allocates buckets and
would no longer exercise cleanup. Final follow-up: **4 passed, 0 failed, 0 skipped** in
14.86 seconds, including a real PostgreSQL 16 version check and the reset email worker
using its recording adapter:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_rate_limit_capacity.py::test_public_capacity_reclaims_public_rows_despite_older_private_budgets tests/integration/test_database.py tests/integration/test_background_job_handlers.py::test_password_reset_handler_reconstructs_active_token_and_finalizes_job -vv -p no:cacheprovider --tb=short
```

Final inventory contains only the seven additional mapped paths relative to the initial
dirty worktree. `rtk git diff --check` passed; the Git index was not changed.

## Review and remaining limits

This is focused remediation evidence, not a claim that the entire repository is free of
vulnerabilities. Full-repository coverage, browser E2E, live proxy/load testing and deployed
behavior are not part of this local correction. No production rollout has occurred.
The byte limit bounds individual body buffering; it does not replace infrastructure
connection/concurrency/time limits. Timing-side-channel equivalence is not established.

## Selective staging plan — not executed

No commit or index update is authorized. Preserve these coherent boundaries if separately
approved later; retain all unrelated existing worktree changes and `Photos/`.

1. `fix(auth): preserve recovery during anonymous budget saturation`
   - `backend/app/services/password_recovery.py`
   - `backend/tests/api/test_password_recovery.py`
   - `backend/tests/api/test_rate_limit_capacity.py`
2. `fix(api): bound request bytes before parsing`
   - `backend/app/core/request_body.py`
   - `backend/app/main.py`
   - `backend/tests/api/test_request_body_limit.py`
3. `docs: record security correction verification`
   - `docs/testing/security-fixes-cra-234.md`

CRA-234 remains In Progress pending owner acceptance. The attempted verification-summary
append to Linear was rejected by automatic approval review as sensitive external egress;
the final verification details were therefore retained locally, not posted to the issue.
