# CRA-150 — logout of other devices

Denys requires this before the demo. `POST /auth/logout-all` implements the existing FINAL API
contract: revoke other sessions of the authenticated User and preserve the current session.
The shared logout control offers `Вийти з інших пристроїв`, with pending, safe error/retry and
success feedback. It does not clear the cookie, navigate away or accept a target User/Session.

Commit boundaries (not authorized): backend sessions service/auth route/API regression;
frontend LogoutButton/component test/browser test; this evidence and current navigation docs.
No migration, dependency, provider action, Git staging or deployment.

## Verification — 2026-09-09

- API RED: 404 instead of 204. Frontend RED: two missing-action failures. Initial sandbox
  Vitest startup failed with Windows EPERM; the same command ran outside the sandbox.
- PostgreSQL/API GREEN: **33 passed, 0 failed, 0 skipped** in 132.46s across
  `test_auth_logout_others.py`, `test_auth_csrf_logout.py`, `test_auth_session.py`,
  `test_password_recovery.py`, `test_employee_lifecycle.py`. Includes the earlier 14-pass subset.
- Focused Vitest: **9 passed, 0 failed, 0 skipped**, LogoutButton and EmployeeProfilePage.
- Playwright: **3 passed, 0 failed, 0 skipped**, `e2e/logout-others.spec.ts`, all three configured
  viewports. Exact POST/CSRF, failure/retry, keyboard activation, retained page and no horizontal
  overflow. Early fixture attempts omitted Pending profile data, then produced a second alert;
  supplying the complete synthetic profile corrected those test setup failures.
- Ruff check, strict mypy and frontend typecheck pass. Formatting applied only to mapped files.

Protected-boundary review: session User ID and preserved Session ID come from the authenticated
dependency. Existing Origin and CSRF validation runs first. The SQL update filters that User,
unrevoked rows and excludes current ID; default all-session revocation behavior remains unchanged
for existing callers. Audit contains only revoked count and non-secret IDs. Repeated requests
return 204 with zero further revocations. Actual revoked-token rejection and another User's
continued access are exercised through the API. This revokes sessions existing at the action,
not future successful logins. Browser tests use mocked APIs; hosted acceptance remains pending.
