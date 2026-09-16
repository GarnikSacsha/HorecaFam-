# CRA-171 — one-time staging account provisioning

## Current evidence — 2026-09-16

Provisioning is no longer an outstanding setup step. The September 12 read-only preflight
recorded existing Organization/Admin access; the September 16 authenticated Dashboard shows
one active Employee and zero awaiting activation. Do not repeat bootstrap, account provisioning
or activation. This does not establish full CRA-171 owner acceptance or a complete Employee
learning journey. Follow [STATUS](../../STATUS.md) and the
[reconciliation ledger](reconciliation-2026-09-16.md).

## Historical committed checkpoint — 2026-09-11

The authorized six-file checkpoint is committed as `0956e7b`. Migration and API rollout later
used that isolated source export. At that checkpoint account provisioning was still unperformed
on staging; the later current evidence above supersedes that account-state observation.

## Scope and authority

Denys selected protected one-time Admin setup on September 11. An owner provisioning cabinet is
deferred. Denys arranges Alexandra's Organization Admin access; Alexandra invites employees via
the existing Organization-scoped invitation UI. Technical Platform Operator and demo Admin remain
different Users. No additional operational role, public endpoint, dependency or migration is added.

The CLI is an owner-controlled database-console operation, not an email-authenticated API.
`--operator-email` identifies the active operator for validation and audit attribution; it is not
proof of the caller's identity. Access to the private console and scoped DB credential is the
execution authority. Never expose this operation through a web route or run it for untrusted input.

## Ordered boundaries and files

1. Initial operator: `backend/app/operations/provision_access.py` and initial-operator cases in
   `backend/tests/integration/test_provision_access.py`.
2. Separate organization Admin, target guard and private CLI: same module/integration file plus
   `backend/tests/unit/test_provision_access_cli.py`. Preserve coherent staged trees when splitting;
   no broken entrypoint or tests referencing the later operation in an earlier checkpoint.
3. This report and CRA-171 navigation in STATUS and the existing staging acceptance runbook.

Denys authorized implementation/tests and one selective local CRA-171 commit. Earlier
CRA-122 synchronization is a separate documentation boundary. Exclude all existing Photos,
outputs, environment files, deployment JSON drafts and unrelated documentation hunks.

Final commit-map refinement: the three implementation stages above share one new CLI entrypoint
and integration suite. Package their verified final outcome as one coherent checkpoint:
`feat(operations): add guarded one-time staging account provisioning`. Select exactly the three
new Python files, this report, and only CRA-171 navigation hunks in STATUS.md and
docs/testing/README.md. Do not include the earlier CRA-122 synchronization or untracked staging
runbook. This exact local checkpoint is authorized; push and deployment are not authorized.

## Behavior and safety

Both commands default to dry-run and require the explicit environment, configured host, database
name and database user. Only test/staging is allowed. Connected database/user and the exact
`0019_auth_security_budgets` revision must match. Use the reviewed private maintenance/migrator
connection; the application runtime role deliberately need not read `alembic_version`.

Initial creation refuses existing partial identities, other platform identities and revoked
platform state. An identical active operator replays without a password change or new audit row.
Admin creation requires an active operator and active exact Organization. It refuses the operator
as target and any target with platform-access history. An existing password-capable User requires
`--reuse-existing`; existing credentials and history remain intact. Revoked/ambiguous organization
access requires a separate recovery decision. Existing active identical access replays unchanged.

New passwords use the existing PasswordManager and 8–128 character policy. `--apply` prompts twice
through hidden terminal input only when creating a new User. No password argument, file, stdin
pipe or echo fallback is accepted. Do not enter passwords into chat or recorded agent terminals.
Use the owner's private interactive console. Errors suppress SQL/validation payloads; after an
uncertain connection/commit outcome inspect state before retrying, rather than assuming rollback.

One transaction owns User, AdminAccess and audit; advisory/row locks serialize setup. No email
verification timestamp, Session, MFA credential, recovery code, Employee membership or activation
is manufactured. Complete normal password login and MFA enrollment separately. Audit contains
actor/target/organization IDs and action/outcome, not email/password/hash.

## Execution sequence — not executed on staging

After separate artifact/migration/account-apply authorization:

1. Run the exact reviewed artifact in the private staging console, with its scoped connection.
   Confirm environment, host, database, DB user and migration 0019 without exposing credentials.
2. Dry-run initial operator, then repeat with `--apply`; owner enters the password privately.
3. Use the existing `app.operations.bootstrap_venue` reviewed non-secret spec, dry-run/apply/replay,
   to obtain the exact Organization ID. That existing operation grants organization access to the
   technical operator as documented; it does not substitute that identity for Alexandra.
4. Dry-run the separate organization Admin, then repeat with `--apply`. For an already-existing
   password-capable User, review identity ownership before adding `--reuse-existing`.
5. Each human completes normal login/MFA. Alexandra then invites employees by email, completes
   their profiles and explicitly activates them. Invitation email delivery/recipients retain their
   provider approval boundary. No automatic training access is granted by invitation acceptance.

Command shapes below contain non-secret placeholders only; replace them with reviewed values:

```text
python -m app.operations.provision_access initial-operator --email <operator-email> --confirm-environment staging --expected-host <private-host> --expected-database railway --expected-db-user <maintenance-user>
python -m app.operations.provision_access organization-admin --email <admin-email> --operator-email <operator-email> --organization-id <organization-uuid> --confirm-environment staging --expected-host <private-host> --expected-database railway --expected-db-user <maintenance-user>
```

Appending `--apply` changes the operation from planning to writing and is separately authorized.
No app account or provider email has been created/sent on staging in this implementation.

## Verification

RED evidence on real dedicated PostgreSQL: initial operator returned planned instead of created
(1 failed); separate Admin likewise returned planned (1 failed, 1 passed); production target guard
failed to reject (1 failed, 2 passed). These are intended behavior failures, not import/setup errors.

Final GREEN: 29 passed, 0 failed/errors/skipped in 78.20 seconds across provisioning integration,
CLI, existing venue bootstrap and MFA/RBAC suites. A newly provisioned Admin's real API password
login returns `mfa_enrollment_required` without a session cookie or platform access.
Ruff format (257 files), Ruff check and strict mypy (235 source files) pass.

Exact focused command, from backend after the guarded `.harness/TESTING.md` test loader:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_provision_access.py tests/unit/test_provision_access_cli.py tests/integration/test_bootstrap_venue.py tests/api/test_auth_mfa_rbac.py -q -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
```

Fresh separated source review checked the console trust boundary, environment/revision checks,
transaction rollback, serialization, target/operator separation, password input/error output and
unchanged API MFA guards. No endpoint or session bypass was added. Full backend coverage, frontend,
Docker, hosted email/storage and staging acceptance are not refreshed by this focused change.
The September 10 865-test report describes the previous source snapshot, not CRA-171.

Documentation verification: 193 relative links checked across the 13 touched synchronization/
acceptance documents, 0 broken. `git diff --check` passed before selective staging. The pre-existing
question_generation.py status mark still has no textual diff. Protected material is preserved.
