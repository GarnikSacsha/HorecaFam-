# Backend MVP Vertical Slice 1 — Stage 7 Acceptance Evidence

## Status and boundary

This document records the local CRA-40 candidate executed on 2026-08-27 against Python 3.12.10
and native PostgreSQL 16. CRA-39 is accepted and Done. CRA-40 is In Progress pending Denys's
acceptance of its three local checkpoints. Push, staging, provider use, deployment, PR, merge,
history rewriting, and non-test data operations were not authorized or executed.

Stage 7 changes tests and evidence only. It introduces no runtime code, API or data-contract
change, dependency, schema object, migration, worker, provider integration, frontend behavior, or
training-domain implementation.

## Requirement-to-evidence matrix

| CRA-13 / CRA-40 gate | Evidence | Result |
|---|---|---|
| Unit | Complete `tests/unit` suite inside the full run | Passed, no skips |
| Real PostgreSQL integration | Complete `tests/integration` suite on dedicated `horeca_test` | Passed, no skips |
| API contract and error envelope | Complete `tests/api` suite plus exact Stage 7 response assertions | Passed |
| Concurrency and idempotency | Invitation and Activation same-key/different-key suites plus Stage 7 Activation replay | Passed |
| CSRF, MFA, RBAC, tenant isolation | Existing security suites plus real Admin login/MFA in the Stage 7 chain | Passed |
| Complete happy path | `test_complete_backend_slice_from_admin_login_to_active_employee_access` | Passed |
| Pending and Disabled restrictions | Pending denial in the complete chain and dedicated Disabled Active-guard denial | Passed |
| Migration smoke | Empty database to head test, `upgrade head`, `current --check-heads`, `alembic check` | Passed |
| Coverage | Overall and declared critical aggregate with branch data | 94.05% / 91.80% |
| OpenAPI and secret fields | 17-path inventory, eight required paths, forbidden-field scan | Complete; zero missing/hits |
| Secret/log/debug/local-path review | Exact changed-path and Git inventory scan | No blocking finding |
| Staging smoke | Requires separate remote/resource authorization | Not run; explicitly deferred |

## Complete backend acceptance path

The new acceptance test executes one uninterrupted business path using the existing application
and real PostgreSQL state:

1. create an Organization, active Role/Location, and password/MFA-capable Organization Admin;
2. authenticate the Admin through `POST /auth/login` and `POST /auth/mfa/verify`;
3. create an Invitation through the protected Organization route with CSRF and idempotency;
4. verify persisted BackgroundJob and EmailDelivery records;
5. run the real invitation-delivery service with a fake adapter that receives the raw token only
   at the delivery boundary;
6. accept the Invitation as a new User and receive a Pending Membership and employee Session;
7. prove that Pending access fails the existing Active employee guard;
8. find and complete the EmployeeProfile through Admin HTTP reads/PATCH while Membership remains
   Pending;
9. activate through the protected idempotent endpoint and replay the same key without duplicate
   effects;
10. reuse the same employee Session to pass the Active guard and read the updated own profile.

The test additionally checks safe responses, token/password non-exposure, exact lifecycle state,
the two API idempotency records, one audit per required business transition, no Activation-created
Session, and the explicit zero-content/zero-assignment/zero-notification applicability result.

## Focused and adjacent evidence

The first combined run reported one passing complete path and one invalid test setup failure:
`EmployeeProfile` was constructed with a nonexistent `organization` relationship. This was not a
product RED and did not justify a runtime change. The test setup was corrected to use the existing
`organization_id` boundary.

After correction:

- `tests/api/test_vertical_slice_acceptance.py`: 2 passed, 0 failed, 0 skipped;
- adjacent auth/login/MFA, invitation create/accept/delivery, employee profile/activation/security,
  and applicability selection: 85 passed, 0 failed, 0 skipped;
- targeted Ruff format/check and mypy: passed.

No production file changed because the complete accepted Stage 0–6 behavior was already coherent.

## Full local gate

Commands were run from `backend/` after loading ignored `.env.test` values without printing them
and validating `APP_ENV=test` plus the dedicated `horeca_test` database name.

```powershell
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing
rtk ..\.venv\Scripts\python.exe -m coverage json -o .coverage-stage7.json
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini current --check-heads
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Results:

- Ruff format: 94 files already formatted;
- Ruff check: passed;
- strict mypy: 86 source files, no issues;
- pytest: 213 passed, 0 failed, 0 skipped in 153.45 seconds;
- exact overall statement/branch coverage: 94.05%;
- Alembic head: `0005_invitation_email_outbox`;
- current-head check: passed;
- autogenerate drift: no new upgrade operations;
- generated `.coverage-stage7.json`: used only for the aggregate calculation and then removed.

## Declared critical aggregate

The Stage 7 critical set contains these 17 first-slice authorization and lifecycle files:

- `app/api/dependencies/auth.py`
- `app/api/dependencies/session.py`
- `app/api/routes/auth.py`
- `app/api/routes/invitations.py`
- `app/api/routes/employees.py`
- `app/security/invitation_tokens.py`
- `app/security/mfa.py`
- `app/security/passwords.py`
- `app/security/tokens.py`
- `app/services/auth.py`
- `app/services/sessions.py`
- `app/services/invitations.py`
- `app/services/invitation_delivery.py`
- `app/services/invitation_acceptance.py`
- `app/services/idempotency.py`
- `app/services/employees.py`
- `app/services/applicability.py`

Coverage.py JSON totals were aggregated as
`(covered statements + covered branches) / (statements + branches)`: `1277 / 1391 = 91.80%`.
This passes CRA-13's critical first-slice threshold of at least 90%.

## OpenAPI and security review

The production application schema contains 17 paths. The following eight required first-slice
paths are present:

- `/api/v1/auth/login`
- `/api/v1/auth/mfa/verify`
- `/api/v1/organizations/{organization_id}/invitations`
- `/api/v1/invitations/accept`
- `/api/v1/organizations/{organization_id}/employees`
- `/api/v1/organizations/{organization_id}/employees/{employee_id}`
- `/api/v1/organizations/{organization_id}/employees/{employee_id}/activate`
- `/api/v1/me/profile`

The serialized schema contains none of `password_hash`, `token_hash`, `csrf_token_hash`,
`secret_encrypted`, or `raw_token`. The final changed-path review found no real credential,
database URL, private key, absolute local path, debug statement, or generated coverage JSON.
Synthetic passwords, tokens, and keys remain confined to test code. Activation still emits no
new Session and its audit values contain no employee names.

## Source dispositions and limitations

- Password reset remains outside the implemented first-slice contract and was not invented.
- Active access is proved through the existing authorization guard/test probe because dashboard,
  Menu, Training, and Assignment APIs are later scope.
- Disabled denial is proved at the existing Active guard; no Disable/Reactivate endpoint was added.
- Zero Published content is a valid Activation outcome; no placeholder content or assignment was
  created.
- The fake email adapter proves the token reconstruction/delivery boundary but is not an external
  provider or deployed worker smoke test.
- Staging smoke was not run because push, deployment, provider, and staging resources require a
  separate bounded issue and explicit authorization.

## Contract impact

API contract: none. Data model and migrations: none. Runtime architecture: none. Provider and
deployment impact: none. The only executable addition is Stage 7 acceptance coverage.
