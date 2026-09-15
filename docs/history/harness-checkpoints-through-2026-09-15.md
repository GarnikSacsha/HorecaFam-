# Historical harness snapshots through 2026-09-15

Archived evidence only. These dated states and next-action lists do not authorize work. Use [current STATUS](../../STATUS.md) and the active bounded Linear issue. The complete pre-cleanup instruction texts are retained below; relative links were rebased.

## Snapshot: .harness/GIT-WORKFLOW.md

<details>
<summary>Historical full text</summary>

# HoReCa Git Workflow

## Current staging state — after API rollout, 2026-09-11

Follow the [verified staging checkpoint](../../STATUS.md#verified-staging-checkpoint--2026-09-11-after-api-rollout).
CRA-171 is committed at `0956e7b`; migration and runtime grants completed in the preceding task,
and API/web are running. Worker, account setup and authenticated acceptance remain open.
The earlier snapshot below is historical and must not drive repeated migration or setup actions.

## Earlier current checkpoint — 2026-09-11, before migration/API rollout

The local demo implementation is committed through `ede4281` (16 checkpoints ahead of
GitHub `fafec73`, behind 0; direct remote read September 11). The exact ledger and recorded
September 10 verification are in [the candidate report](../../docs/testing/demo-candidate-2026-09-10.md).
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

## Current baseline state — 2026-09-08

Published local main, origin/main and the direct GitHub ref match `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`.
CRA-125's ten commits end at `2275cee`; CRA-126's four commits follow through `fafec73`.
All are published. Formal corrective acceptance and deployment-candidate selection are distinct.
The Git index is empty; existing documentation changes, Photos, outputs and the metadata-only
question_generation.py mark remain local. No staging/commit/push is authorized by synchronization.
The two exact documentation commit boundaries are recorded in [STATUS.md](../../STATUS.md).
Global harness pin and operating rules remain unchanged. See STATUS for current evidence and
CRA-122 for the last accepted staging SHA; a mutable main branch is not deployment approval.

## Mandatory rules

- Resolve the repository root and inspect `git status --short --branch` before any Git action.
- Preserve unrelated and user-authored files.
- Define the bounded task's ordered commit map before implementation starts.
- Never use `git add .`; stage only the exact reviewed paths declared for the current map entry.
- Do not commit unless Denys has explicitly authorized local commits for the bounded task and its
  agreed map.
- Push, PR, merge, deploy, remote configuration, and history rewriting are independent approval
  gates. Local-commit authorization grants none of them.
- Do not use destructive Git commands to simplify the worktree.
- Treat accepted checkpoint commits as recoverable project history, not disposable snapshots.

## Commit map contract

Before implementation, write an ordered map whose every entry includes:

1. one coherent behavior or documentation/process outcome;
2. expected production, test, migration, configuration, and directly corresponding documentation
   paths, as applicable;
3. the focused verification that proves the stage is GREEN;
4. an intended descriptive commit message;
5. dependencies on earlier map entries and the remaining excluded scope.

Commit boundaries follow coherent behavior, not file count, elapsed time, token budget, or
arbitrary diff size. Code, focused tests, migrations, and directly corresponding documentation
stay together when they are required for one behavior. Independently useful or reversible
outcomes use separate map entries.

The map may change when implementation evidence reveals a different coherent boundary. Record
the reason, update the remaining map before continuing, and do not use the change to expand the
bounded Linear scope silently.

## Local-commit authorization

One explicit authorization for local commits in a bounded Linear issue covers all selective
commits in that issue's agreed map. The agent does not ask again before every mapped commit.

That authorization does not permit:

- paths or behavior outside the bounded issue and map;
- push, PR, merge, release, Railway, or deployment;
- remote creation or reconfiguration;
- squash, amend, rebase, reset, force-push, or another history rewrite.

If local commits are not authorized, preserve the same logical boundaries in the worktree and
report an exact selective staging plan for every proposed commit. Do not change the Git index.

## GREEN checkpoint sequence

For every mapped implementation stage:

1. produce and record the smallest meaningful failing `RED` test when behavior changes;
2. confirm RED fails because the intended behavior is missing, not because setup is broken;
3. implement the smallest coherent change to reach `GREEN`;
4. refactor while the focused and proportionate adjacent checks remain green;
5. run the verification declared by the map entry;
6. inspect the exact diff for scope, secrets, local paths, generated artifacts, and unrelated
   changes;
7. when local commits are authorized, selectively stage the declared paths, verify the staged
   inventory and `git diff --cached --check`, then create one atomic commit;
8. confirm the remaining worktree still matches the uncompleted map before starting the next
   independent stage.

A broken RED state is evidence, not a checkpoint: never commit it knowingly. Documentation-only
work may use its declared TDD exception and documentation verification instead, but it becomes a
commit checkpoint only after those checks pass.

## Checkpoint preservation and recovery

Do not squash, amend, rebase, reset, or otherwise rewrite an accepted checkpoint commit without
separate Denys approval. Once history is shared, recover a bad checkpoint with a new revert or
corrective commit so the earlier state remains reachable and auditable.

An unaccepted local checkpoint may still be corrected only within the current explicit authority;
never infer history-rewrite permission from permission to commit.

## Published baseline boundary

The initial published backend/docs baseline contains the 43 paths accepted in the five-commit
CRA-23 map, plus the later documentation-only repository-state synchronization checkpoint. The
baseline intentionally excludes:

1. `Photos/`, which contains CRA-19 homepage project assets and remains untouched, unignored, and
   unstaged unless a separate approved map explicitly includes those assets;
2. local artifacts such as `.venv`, `.pydeps`, `.env*`, caches, coverage files, installers, and
   acceptance helpers, which are never baseline content.

Publication of any checkpoint does not authorize the next implementation stage. Every subsequent
change still requires an active bounded Linear issue, an agreed commit map, and the applicable
local-commit and remote-action approvals. The accepted historical checkpoints through CRA-75 are
recorded in Linear and the repository evidence index. CRA-77 is accepted and published as part of
the baseline through `c8a1135`; CRA-119 is accepted, Done, and published through `2644b796`.
CRA-122 is the active deployment task. Every later push, PR, merge, history rewrite, provider,
resource, secret, deployment, and non-test data action remains separately gated.

</details>

## Snapshot: .harness/TESTING.md

<details>
<summary>Historical full text</summary>

# HoReCa Testing and Quality Commands

## Current staging state — after API rollout, 2026-09-11

Follow the [verified staging checkpoint](../../STATUS.md#verified-staging-checkpoint--2026-09-11-after-api-rollout).
CRA-171 is committed at `0956e7b`; migration and runtime grants completed in the preceding task,
and API/web are running. Worker, account setup and authenticated acceptance remain open.
The earlier snapshot below is historical and must not drive repeated migration or setup actions.

## Earlier current checkpoint — 2026-09-11, before migration/API rollout

The local demo implementation is committed through `ede4281` (16 checkpoints ahead of
GitHub `fafec73`, behind 0; direct remote read September 11). The exact ledger and recorded
September 10 verification are in [the candidate report](../../docs/testing/demo-candidate-2026-09-10.md).
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

## Current verification — 2026-09-08

Published source: `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`; migration head: `0019_auth_security_budgets`.
CRA-126 records one full PostgreSQL 16 run: **832 passed, 0 failed, 0 errors, 0 skipped**.
Statements **11532/12286 (93.86%) PASS**; branches **2064/2574 (80.19%) PASS**;
fixed nine-file critical aggregate **1319/1471 (89.67%) PASS**.
Ruff format/check, strict mypy and test-DB Alembic checks passed in that recorded gate.
The September 8 audit reevaluated the saved full-run coverage report; no full suite rerun is claimed.
CRA-125's 809-pass gate and earlier failed branch gates remain historical, with unchanged thresholds.
Latest frontend evidence remains September 7: 72 Vitest, 42 Playwright and 5 artifact/topology
checks passed with zero failures/skips; CRA-126 did not rerun browser/container/provider suites.
Local results do not prove live staging acceptance. Formal issue acceptance remains explicit.
See [CRA-126 report](../../docs/testing/security-fixes-cra-126.md) and [current status](../../STATUS.md).

<details>
<summary>Historical CRA-125 and September 7 audit checkpoints</summary>

## Latest local CRA-125 evidence

The latest fresh full PostgreSQL 16 run passed **809 tests, 0 failed, 0 skipped in 1984.30s**.
Independent gates: statements **11408/12135 = 94.01% PASS**; branches
**2041/2538 = 80.42% PASS**; fixed critical aggregate **1293/1443 = 89.60% PASS**.
The helper verifies complete source inventory and unchanged thresholds with raw counts.
Ruff format/check (238 files) and strict mypy (217 source files) pass. All three authorized
corrections are GREEN. Denys authorized the ten local commits; the nine app/test checkpoints
are committed through `b9a66e8`, with the final documentation checkpoint recording their evidence.
Each mapped focused suite and Ruff/mypy check passed; Python sources still match the 809-pass
run. No push or staging deployment occurred. The lower audit metrics below remain historical. Follow the
[current execution record](../../docs/testing/coverage-closure-plan.md) for exact evidence.

## Current audit and evidence boundary — 2026-09-07

[Exact September 7 results](../../docs/testing/repository-audit-2026-09-07.md): 552 backend tests, 72 Vitest tests,
42 Playwright executions and 5 artifact/topology tests passed with zero failed/skipped tests.
Ruff, mypy, frontend format/lint/types/build, topology typecheck and Alembic checks passed.
Published source: `e18af71`; schema head: `0018_job_runtime`.

Overall coverage: **89.22% statements / 67.76% branches / 85.51% combined**. CRA-77 critical set:
85.19% / 64.89% / 81.22%. Older “86% statement/branch” records describe the combined metric;
they are not evidence of separate 86% branch coverage. Denys approved independent overall
thresholds of at least 80% statements and at least 80% branches on September 7 (CRA-13).
Statements pass; branches fail. The critical aggregate threshold remains at least 80%.
CRA-125 implements the approved [coverage closure plan](../../docs/testing/coverage-closure-plan.md).
The new `tests.coverage_gate` helper verifies both raw-count thresholds, the fixed critical
aggregate and complete application source inventory. Its 16 unit cases pass; the saved audit
correctly fails the original audit's branch gate. The latest full run above passes all gates.
Preserve historical acceptance and report current metrics separately.

The following stage results retain their original evidence dates. Documentation synchronization
does not rerun the application suites. Local mocks/signing tests do not prove live staging.



</details>

## Supported baseline

- Python: 3.12 only, as constrained by `backend/pyproject.toml`.
- Database: real PostgreSQL 16 for integration and migration tests.
- Local boundaries: `compose.test.yml` or native PostgreSQL 16.
- SQLite fallback: prohibited.
- Test environment: `APP_ENV=test` and a dedicated database named `horeca_test` or an approved
  worker-scoped derivative.

The published repository includes the accepted CRA-48 corrective record after `3b95b3c`.
CRA-43 runtime acceptance evidence remains anchored to its implementation endpoint `fa30a1f`.
CRA-47 planning and CRA-48 documentation are Done. CRA-49 is accepted and fast-forward published
through corrective checkpoint `8028d6e`; its evidence is recorded in
[`../docs/testing/menu-slice-2-acceptance.md`](../../docs/testing/menu-slice-2-acceptance.md).
CRA-53 planning and CRA-54 implementation are accepted and Done. CRA-54 is published through
`d955f6a`; its evidence is recorded in
[`../docs/testing/training-slice-3-acceptance.md`](../../docs/testing/training-slice-3-acceptance.md).
CRA-55 documentation synchronization and CRA-56 Slice 4 planning are Done. CRA-57 is accepted,
Done, and fast-forward published through `d4e0184`; its evidence is recorded in
[`../docs/testing/training-assignment-slice-4-acceptance.md`](../../docs/testing/training-assignment-slice-4-acceptance.md).
CRA-60 planning and CRA-61 Interactive Training are accepted and Done. CRA-61 evidence is recorded in
[`../docs/testing/interactive-training-slice-5-acceptance.md`](../../docs/testing/interactive-training-slice-5-acceptance.md).
CRA-63 Practice planning and CRA-64 implementation are accepted and Done. CRA-64's exact evidence
is recorded in
[`../docs/testing/practice-slice-6-acceptance.md`](../../docs/testing/practice-slice-6-acceptance.md).
CRA-65 synchronization is published through `4164b9c`. CRA-66 Final Exam planning and CRA-67
implementation are accepted and Done; exact CRA-67 evidence is recorded in
[`../docs/testing/final-exam-slice-7-acceptance.md`](../../docs/testing/final-exam-slice-7-acceptance.md).
CRA-68 is Done and published through `9ef9fe1`. CRA-69 Slice 8 planning and CRA-71 Attention and
Retakes are accepted and Done. CRA-74 ordinary fast-forward published CRA-70 at `5352f89`, CRA-71
as `62a80a0..054d731`, and the CRA-72 documentation checkpoint through `4019262`. CRA-75 owns the
publication-state documentation checkpoint. Exact accepted evidence is recorded in
[`../docs/testing/attention-retakes-slice-8-acceptance.md`](../../docs/testing/attention-retakes-slice-8-acceptance.md).

## Environment setup

Run from the repository root:

```powershell
rtk py -3.12 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
```

Docker Compose remains a supported boundary when Docker is available:

```powershell
rtk docker compose -f compose.test.yml up -d --wait
```

The accepted local fallback is native PostgreSQL 16. Store native or Compose test values only in
the ignored `backend/.env.test`; never paste its values into documentation, Linear, logs, or Git.
The file uses these keys with local values:

```dotenv
APP_ENV=test
TEST_DATABASE_URL=<local-test-postgresql-async-url>
DATABASE_URL=<same-local-test-postgresql-async-url>
```

Before a PostgreSQL gate, load the ignored file into the current PowerShell process without
printing it:

```powershell
$testEnvPath = Resolve-Path .env.test
foreach ($line in [IO.File]::ReadAllLines($testEnvPath)) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { continue }
    $parts = $line.Split(@("="), 2, [StringSplitOptions]::None)
    if ($parts.Count -ne 2) { throw "Invalid .env.test entry." }
    [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
}
if ($env:APP_ENV -ne "test") { throw "APP_ENV=test is required." }
if ($env:TEST_DATABASE_URL -notmatch "/horeca_test(?:_[a-z0-9]+)*$") {
    throw "A dedicated horeca_test database is required."
}
```

Run this snippet from `backend/`. Do not echo the resulting variables.

## Exact project commands

After a successful fresh full coverage run, generate and evaluate the report from `backend/`.
The report must come from that same successful run; do not reuse an old JSON after an error.
Keep generated evidence in the ignored test cache and out of Git:

```powershell
rtk ..\.venv\Scripts\python.exe -m coverage json -o .pytest_cache/cra125/current.json
rtk ..\.venv\Scripts\python.exe -m tests.coverage_gate .pytest_cache/cra125/current.json
```

Exit codes: 0 means all three gates pass; 1 means a threshold fails; 2 means report validation
failed. Combined `--cov-fail-under` alone cannot enforce the two independent overall gates.

Run from `backend/`:

```powershell
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini current --check-heads
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Example targeted commands:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_health.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_database.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_identity_models.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/migration/test_migrations.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_auth_login.py tests/api/test_auth_session.py tests/api/test_auth_csrf_logout.py tests/api/test_auth_mfa_rbac.py -vv -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_invitations_create_validate.py tests/api/test_invitations_resend_revoke.py tests/integration/test_invitation_services.py -vv -p no:cacheprovider
```

The full gate is not green when required PostgreSQL tests are skipped. Report passed, failed, and
skipped counts explicitly.

## Accepted Stage 0 evidence

CRA-20 was accepted on 2026-08-26 with Python 3.12.10 and native PostgreSQL 16.15:

- 22 passed, 0 failed, 0 skipped;
- 95% Stage 0 statement/branch coverage;
- live async SQLAlchemy/asyncpg round-trip;
- fresh database upgraded to Alembic head `0001_stage0`;
- Ruff format, Ruff check, and mypy passed.

This is historical accepted evidence, not a substitute for rerunning checks after behavior changes.
See [`../docs/testing/README.md`](../../docs/testing/README.md) and the canonical CRA-20 evidence in
Linear.

## Accepted Stage 1 evidence

CRA-28 was accepted with a local Python 3.12.10/PostgreSQL 16.15 gate reporting 47 passed,
0 failed, 0 skipped, 97% coverage, Alembic head
`0002_identity_persistence`, and no metadata drift. Rerun the complete gate before relying on this
snapshot or preparing any authorized commit.

## Accepted CRA-30 Stage 2 evidence

The accepted CRA-30 checkpoint uses the same Python 3.12.10 and native PostgreSQL 16.15 boundary.
Its final complete gate reports 92 passed, 0 failed, 0 skipped, 94% overall statement/branch
coverage, 92% critical auth coverage, Alembic head `0003_auth_security`, and no metadata drift.
Canonical evidence remains in Linear.

## Accepted CRA-32 Stage 3 evidence

The accepted CRA-32 invitation checkpoint uses Python 3.12.10 and native PostgreSQL 16.15. Its
complete gate reports 156 passed, 0 failed, 0 skipped, 94% overall statement/branch coverage, 90%
aggregate critical invitation coverage, Alembic head `0005_invitation_email_outbox`, and no
metadata drift. Canonical evidence remains in Linear.

## Accepted CRA-34 Stage 4 evidence

The accepted invitation-acceptance checkpoint uses the same Python 3.12.10 and native PostgreSQL 16.15
boundary. Its final gate reports 180 passed, 0 failed, 0 skipped, 94% overall statement/branch
coverage, 93% aggregate critical acceptance coverage, Alembic head
`0005_invitation_email_outbox`, and no metadata drift. Focused API acceptance reports 12 passed.
CRA-34 is Done and its four commits are published through `9fd2130`. Canonical evidence remains in
Linear.

## Accepted CRA-36 Stage 5 evidence

The accepted Pending/Admin Profile Setup checkpoint uses Python 3.12.10 and native PostgreSQL 16.
Its complete gate reports 195 passed, 0 failed, 0 skipped, 94% overall branch coverage, and 92%
aggregate critical Stage 5 coverage. Focused Stage 5 API/integration reports 15 passed. Alembic
remains at `0005_invitation_email_outbox`; the empty-database migration test, current head check,
and metadata no-drift check pass. Canonical acceptance and publication evidence remains in Linear.

## Accepted CRA-38 Stage 6 evidence

The Explicit Activation candidate uses Python 3.12.10 and native PostgreSQL 16. Its complete gate
reports 211 passed, 0 failed, 0 skipped, 94% overall branch coverage, and 92% coverage for
`app/services/employees.py`. Focused Stage 6 API/integration/security checks cover the exact
response, preconditions, CSRF/MFA/RBAC, tenant isolation, idempotency replay and key reuse,
same-key/different-key concurrency, rollback, applicability, active access, OpenAPI, no new Session,
and the live Stage 4→5→6 chain. Alembic remains at `0005_invitation_email_outbox`; the
empty-database migration test, current head check, and metadata no-drift check pass. CRA-38 is
accepted, Done, and published as part of the backend baseline through `abad74e`.

## Accepted CRA-40 Stage 7 evidence

The Full Regression and Acceptance Gate candidate uses Python 3.12.10 and native PostgreSQL 16.
Its complete gate reports 213 passed, 0 failed, 0 skipped, 94.05% exact overall statement/branch
coverage, and 91.80% aggregate coverage across the declared 17-file critical first-slice set.
The new acceptance file reports 2 passed; the adjacent auth/invitation/employee security and
integration suite reports 85 passed. Ruff format/check and strict mypy pass. Alembic remains at
`0005_invitation_email_outbox`; empty-database migration coverage, current-head verification, and
metadata no-drift all pass. The OpenAPI inventory contains 17 paths, all eight required first-slice
paths, and none of the forbidden internal secret fields. Canonical command and matrix evidence is
recorded in [`../docs/testing/vertical-slice-1-acceptance.md`](../../docs/testing/vertical-slice-1-acceptance.md).
CRA-40 is accepted, Done, and published through `abad74e`.

## Accepted CRA-43 frontend commands and evidence

Use Node.js 24 and pnpm 11. Run from `frontend/`:

```powershell
rtk pnpm install --frozen-lockfile
rtk pnpm format:check
rtk pnpm lint
rtk pnpm typecheck
rtk pnpm test
rtk pnpm build
rtk pnpm exec playwright install chromium
rtk pnpm test:e2e
```

CRA-43 is accepted, Done, and published through `fa30a1f`. Its component gate contains 13 tests
across nine files. The browser gate executes one
complete route-mocked business path in three projects: 1440×1000 Admin desktop, 768×1024 compact,
and 375×812 employee mobile. Exact scope, RED/GREEN evidence, and limitations are recorded in
[`../docs/testing/frontend-vertical-slice-1-acceptance.md`](../../docs/testing/frontend-vertical-slice-1-acceptance.md).

Coverage enables the standard `greenlet` concurrency tracer because SQLAlchemy's async adapter
crosses greenlet contexts. Without it, executed post-database branches are under-reported.

## Accepted CRA-49 evidence

The corrective accepted 2026-08-28 gate reports 270 passed, 0 failed, 0 skipped with 89% overall
statement/branch coverage on Python 3.12.10 and native PostgreSQL 16. Denys accepted the precise
coverage closure as at least 80% overall coverage with branch tracking, complete mandatory-scenario
mapping, and explicit concurrency/security proof; no undeclared critical file set is selected
retroactively. Ruff format/check, strict
mypy, Alembic head `0007_menu_import_review`, current-head validation, migration round-trips, and
metadata no-drift all pass. The frontend reports 19 Vitest tests and 6 Playwright tests passing,
with Prettier, ESLint, TypeScript, and production build green. The ten-part implementation ends at
`22927f7`; the corrective acceptance tail is published through `8028d6e`.

## Accepted CRA-54 evidence

The accepted 2026-08-28 gate reports 318 passed, 0 failed, 0 skipped with 88% overall
statement/branch coverage and 80% aggregate coverage across the predeclared seven-file critical
Training set on Python 3.12.10 and native PostgreSQL 16. Ruff format/check and strict mypy pass.
Alembic head is `0008_training_content`; empty-database upgrade, the Training migration round-trip,
current-head validation, and metadata no-drift pass. The frontend reports 27 Vitest tests and
9 Playwright tests passing, with Prettier, ESLint, TypeScript, and production build green.

Denys accepted the candidate and authorized fast-forward publication of its nine checkpoints to
`origin/main` through `d955f6a`. Railway/provider smoke, deployment, PR, merge, and production
configuration were not performed.

## Accepted CRA-57 evidence

The 2026-08-29 local gate reports 363 passed, 0 failed, 0 skipped with 88% overall
statement/branch coverage and 87% aggregate coverage across the seven Slice 4 service files on
Python 3.12.10 and native PostgreSQL 16. Ruff format/check and strict mypy pass. Alembic head is
`0009_assignment_completion_rollout`; current-head, empty-database/round-trip coverage and
metadata no-drift pass. The frontend reports 35 Vitest tests and 12 Playwright executions with
Prettier, ESLint, TypeScript, and production build green.

Denys accepted the implementation and authorized ordinary fast-forward publication of the nine
checkpoint range `5823a0e..d4e0184`. The range is published without history rewriting. No PR,
merge, provider, deployment, production configuration, or production-data action was performed.

## Accepted CRA-61 evidence

The 2026-08-29 local gate reports 424 passed, 0 failed, 0 skipped with 88% overall
statement/branch coverage and 86% aggregate coverage across the predeclared five critical Slice 5
services on Python 3.12.10 and native PostgreSQL 16. Ruff format/check and strict mypy pass.
Alembic head is `0013_question_templates`; 13 migration tests, clean upgrade, current-head validation
and metadata no-drift pass. The frontend reports 45 Vitest tests and 15 Playwright executions,
with Prettier, ESLint, TypeScript and production build green.

Denys accepted this evidence and the remaining source-bound generation limitation. CRA-62 governs
repository publication and exact remote evidence. No PR, merge, provider, or deployment action is
authorized by the acceptance.

## Accepted CRA-64 Practice evidence

The accepted 2026-08-31 eight-checkpoint range adds the ten-Question Practice boundary, final-only
feedback,
durable Final Exam eligibility, Admin readiness and Employee/browser flows. The mandatory
forty-scenario matrix and actual gate results are recorded in
[`../docs/testing/practice-slice-6-acceptance.md`](../../docs/testing/practice-slice-6-acceptance.md).
CRA-64 is Done and CRA-65 synchronization is published through `4164b9c`. Later push, PR, merge,
provider and deployment gates remain separate.

## Accepted CRA-67 Final Exam evidence

The accepted eight-checkpoint range adds balanced 20-question Final Exam readiness and immutable
Attempts, seven-day effective inactivity, feedback-free Answers, explicit finish, exact 70%
passing, critical-error evidence, certification/history, canonical Admin Results and responsive
Employee/Admin flows. The full real-PostgreSQL regression reports 445 passed, 0 failed, 0 skipped
at 85% overall coverage; the new focused real-database acceptance test separately reports 1
passed. Ruff, strict mypy, Prettier, ESLint, TypeScript and production build pass. Full Vitest
reports 57 passed and full Playwright reports 21 passed; final focused reruns report 2 component
tests and 3 browser executions passed. Alembic remains at `0014_practice_persistence`, with
upgrade/current-head/no-drift checks green. CRA-67 and CRA-68 are Done, and the accepted repository
baseline is published through `9ef9fe1`. These results remain historical accepted evidence.

The accepted CRA-71 implementation reports 463 backend tests passed at 86%
statement/branch coverage; Ruff,
strict mypy, Alembic upgrade/current/no-drift at `0015_attention_retakes`, Prettier, ESLint,
TypeScript and production build passed. Full Vitest reports 58 passed and full Playwright reports 27
passed across desktop, compact and mobile. Denys accepted this evidence and the exact
eight-checkpoint range; CRA-74 ordinary fast-forward published it through `4019262`.

## CRA-77 accepted and published Operations and Hardening gate

The authorized thirteen-checkpoint local range `974feeb..ef74be4` was independently revalidated on
Python 3.12.10 and dedicated PostgreSQL 16. The exact full backend command reports 530 passed,
0 failed, 0 skipped in 1334.59s,
86% overall statement/branch coverage and 81% aggregate coverage across the predeclared nine-file
critical set. Ruff format/check and strict mypy pass. Alembic upgrade, current-head and no-drift
pass at `0018_job_runtime`.

Frontend Prettier, ESLint, TypeScript and production build pass. Full Vitest reports 72 passed and
full Playwright reports 42 passed. Browser accessibility-tree, keyboard, contrast and reduced-motion
review also passes within its documented proxy boundary. Exact evidence and limitations are in
[`../docs/testing/operations-hardening-slice-9-acceptance.md`](../../docs/testing/operations-hardening-slice-9-acceptance.md).

The bootstrap command is dry-run-first. Any non-test `--apply`, provider call, deployment, restore
or load test remains separately gated; never infer those permissions from the local test result.

CRA-77 is accepted and published as part of the repository baseline through `c8a1135`.

## CRA-119 accepted and published deployment readiness gate

The accepted seven-checkpoint range `b1d145b..2644b79` reports 544 backend tests passed,
0 failed, and 0 skipped at 86% statement/branch coverage. Ruff format/check, strict mypy,
Alembic current/no-drift at `0018_job_runtime`, frontend format/lint/types/build, 72 Vitest tests,
two frontend deployment-artifact tests, Railway topology typecheck, and three static topology tests
passed. Docker image/container smoke was not executed because the local Linux engine was
unavailable. The range is accepted, Done, and published through `2644b796`.

CRA-121 provisioning is accepted and Done, with provider evidence recorded in Linear and Resend
setup deferred. CRA-122 is active with Stage 1 complete and Stage 2 planning in progress. Local
checks alone do not prove real email, deployed API/worker/cron, migration, backup/restore,
load, or venue UAT. Use the [Stage 2 plan](../../docs/deployment/staging-cra-122.md) before external work.

CRA-123's [local container evidence](../../docs/testing/caddy-delivery-cra-123.md) records the Docker
builds and 9 passing real Caddy HTTP tests, with exact reproduction commands and limitations.
The correction is published as `ec27d19` within `5a1e650`; this is not staging acceptance.
The 2026-09-05 audit reran 72 Vitest and 5 artifact/topology tests, all passed with zero failed
or skipped tests. Docker HTTP checks were not rerun because the Linux engine was unavailable.

</details>

