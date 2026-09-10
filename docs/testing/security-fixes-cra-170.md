# CRA-170 security corrections — 2026-09-09

Scope: [CRA-170](https://linear.app/craftspacee/issue/CRA-170), authorized by Denys after the
September 9 Codex Security review. Current local worktree; no commit or deployment authorization.
Outcome: **fixed locally**. Final focused regression passed; owner acceptance remains pending.

## Boundaries and implementation

1. `change_password` revokes that user's unused, unrevoked reset tokens in the existing
   credential-change transaction. The common User/email lock serializes reset/change/issuance.
   Failed password verification does not revoke tokens. Current-session retention, other-session
   revocation and elevated MFA remain unchanged; a subsequently requested recovery link is valid.
2. `rate_limit_storage.py` caps public bucket allocation at **4096 per table**: combined
   `login/password_forgot/password_reset` actions in the auth table, and `validate` in the
   invitation table (shared by validation and acceptance). Existing exact-subject limits remain.
   New insertions hold a PostgreSQL transaction advisory lock across count and insert/commit.
   Capacity or lock contention returns the existing `429 AUTH_RATE_LIMITED` without allocating.
   Password-token budgets also lock their subject, including nonexistent tokens.
3. At capacity, admission tries to reclaim at most 64 expired rows. Both the 15-minute window and
   any later block must have ended. Row locks with `SKIP LOCKED` protect concurrent refreshes.
   The existing security cleanup job also retires buckets in its bounded batch, respecting its
   existing cutoff/retention contract. No schema, migration, dependency or provider change.

The cap deliberately trades new-subject availability under saturation for bounded storage.
Existing subjects still use their budgets; valid login needs no new failure row. New password
recovery subjects can receive 429 until capacity becomes available. This is not ingress/load
protection or a claim of unlimited availability. Previously accumulated rows above the cap need
the existing authorized cleanup flow; the correction prevents additional public growth, not an
automatic non-test data migration. MFA/reauth and Admin invitation create/resend are not anonymous
allocation paths and do not consume the public cap.

## Ordered selective commit map — not executed

1. `fix(auth): revoke outstanding reset links on password change`
   - `backend/app/services/password_recovery.py`: token-revocation hunk only.
   - `backend/tests/api/test_password_recovery.py`.
   - Gate: recovery and existing security regressions, Ruff and strict mypy.
2. `fix(security): bound public rate-limit state and retire expired budgets`
   - `backend/app/services/rate_limit_storage.py`, `auth.py`, `invitations.py`, `maintenance.py`.
   - `backend/app/services/password_recovery.py`: storage import/locking/admission hunks only.
   - `backend/tests/api/test_rate_limit_capacity.py` and
     `backend/tests/integration/test_maintenance_jobs.py`.
   - Gate: capacity, concurrency, cleanup and adjacent login/invitation/recovery/delivery tests;
     backend Ruff and strict mypy; independent candidate review.
3. `docs: record CRA-170 security correction evidence`
   - This report and only the CRA-170 addition to `STATUS.md`.
   - Gate: evidence/link/diff inventory review. Existing unrelated changes stay separate.

## RED evidence

Commands run from `backend/`, using the secret-safe dedicated PostgreSQL test environment loader
in `.harness/TESTING.md`. No environment values or real user data are recorded here.

- `rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_password_recovery.py -k invalidates_only -q -p no:cacheprovider --tb=short`
  — 1 failed / 1 passed / 0 skipped: old link returned 204 instead of 400 after successful change.
  Failed-change control remained valid. The first `--tb=no` run had the same counts.
- Initial capacity/cleanup suite: 7 failed. Six proved missing admission/cleanup behavior; reset
  initially failed payload validation (422) and is not valid RED evidence. After correcting the
  synthetic token length, `-k 'capacity and reset'` failed on 400 instead of required 429.

## Verification ledger

- Final combined regression: **124 passed / 0 failed / 0 errors / 0 skipped in 335.83s**.
  This includes the final mixed-action reclamation correction and other-user-token assertions.
  Both original findings no longer reproduce through the tested production service/API paths;
  legitimate recovery, login, invitation and worker controls pass alongside them.
- First recovery/security GREEN: 21 passed, 0 failed, 0 skipped.
- Initial capacity/recovery/maintenance GREEN: 42 passed, 0 failed, 0 skipped.
- Added explicit concurrent reset/change ordering, last-slot contention, same-token concurrency,
  cleanup-versus-update locking, valid-login-at-capacity and other-user-token isolation controls.
- Expanded regression before candidate review: 103 passed / 0 failed / 0 skipped in 276.06s.
- One independent read-only candidate review found a reclamation regression: older nonpublic
  actions could fill the 64-row reclaim batch without reducing the public count. Parent reproduced
  both table variants (2 failed / 0 passed / 0 skipped), then restricted admission reclamation to
  the same action set as its capacity count. Periodic cleanup still covers all actions. No other
  concrete surviving bypass was reported. Only one independent review cycle was performed.
- Ruff format/check and strict mypy passed after correcting test formatting and optional/union
  type narrowing. The final combined regression includes the reviewed correction.
- One adjacent command named a nonexistent acceptance test file; no tests ran. The corrected
  command uses `tests/api/test_invitations_accept.py`.

Final regression command (includes all previous focused families and the affected worker handler):

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_rate_limit_capacity.py tests/api/test_password_recovery.py tests/api/test_auth_security_regressions.py tests/api/test_auth_login.py tests/api/test_invitations_create_validate.py tests/api/test_invitations_accept.py tests/integration/test_maintenance_jobs.py tests/integration/test_password_reset_delivery.py tests/integration/test_background_job_handlers.py -q -p no:cacheprovider --tb=short
```

Quality commands from `backend/`: `rtk ..\.venv\Scripts\python.exe -m ruff format --check .`,
`rtk ..\.venv\Scripts\python.exe -m ruff check .`, and
`rtk ..\.venv\Scripts\python.exe -m mypy app tests`.
Final source checks: 254 files formatted, Ruff clean, strict mypy clean across 232 source files.
`git diff --check` passed and the Git index remained empty.

This bounded backend correction uses the focused owning-service/handler regressions and whole
backend static checks. Full product regression/coverage and frontend/browser suites are not
refreshed: UI, schema and unrelated assessment paths are unchanged by CRA-170. Historical full
coverage counts retain their original dates. Test fixtures upgrade and check the dedicated
PostgreSQL database at existing head `0019_auth_security_budgets`.

No production database, live ingress, external provider, browser, or full coverage run is implied
by these focused checks. Published SHA and schema head remain unchanged; local fixes need review,
explicit owner acceptance and separately authorized publication/deployment.
