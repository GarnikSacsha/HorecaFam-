# Repository audit evidence — 2026-09-07

## Boundary and authorization

This document preserves the original published-source audit. Newer uncommitted CRA-125
results (809-test full run, all three coverage gates passing and three approved corrections)
are recorded separately in the [coverage execution record](coverage-closure-plan.md).

Read-only project audit at published main `e18af71f89d587b1cb6b472cf189e67dfa8102a0`.
Denys subsequently authorized repository and Linear state reconciliation under
[CRA-122](https://linear.app/craftspacee/issue/CRA-122/deploy-and-accept-staging).
This record preserves the audit's actual results; documentation edits do not constitute a new
application test run or deployment acceptance. Product/API/schema behavior is unchanged.

## Executed audit gate

| Check | Result |
| --- | --- |
| Python / database boundary | Python 3.12.10; real PostgreSQL 16; dedicated test database |
| Full pytest | 552 passed, 0 failed, 0 skipped; 1324.34 seconds |
| Ruff format / check | Passed; 235 files formatted |
| Strict mypy | Passed; 214 source files |
| Alembic upgrade/current/check | Passed at `0018_job_runtime`; no new upgrade operations |
| Vitest | 72 passed, 0 failed, 0 skipped; 21 files |
| Playwright | 42 passed, 0 failed, 0 skipped; 14 scenarios × 3 viewports |
| Frontend format/lint/types/build | Passed |
| Deployment artifact / topology tests | 5 passed, 0 failed, 0 skipped |
| Railway topology TypeScript | Passed |
| Git diff check / staged inventory | Passed; index unchanged |
| Direct remote main | Matches local main at `e18af71` |
| Railway read-only status | PostgreSQL Online; all nine application services Offline |
| Docker HTTP rerun | Not executed: Linux engine unavailable; historical CRA-123 9 passes remain dated September 4 |

Initial sandbox frontend/node invocations hit process-launch EPERM; authorized retries passed.
An initial PowerShell test-environment command had a parse error before pytest and was corrected.
Neither setup failure is behavior RED. Test environment values were loaded with the existing
Harness procedure without printing them.

## Coverage, measured separately

| Scope | Statements covered/total | Branches covered/total | Statement % | Branch % | Combined % |
| --- | --- | --- | --- | --- | --- |
| All app files | 10820/12127 | 1717/2534 | 89.22 | 67.76 | 85.51 |
| CRA-77 critical set | 989/1161 | 183/282 | 85.19 | 64.89 | 81.22 |

Combined coverage counts statements and branch destinations together; pytest rounds 85.51% to
86%. That number is not separate 86% branch coverage. The unchanged predeclared critical set is
`services/password_recovery.py`, `services/mfa_enrollment.py`, `services/employees.py`,
`services/background_jobs.py`, `services/background_job_handlers.py`, `services/maintenance.py`,
`services/operator_jobs.py`, `core/observability.py`, and `operations/bootstrap_venue.py`.

CRA-13/CRA-77 say “≥80% overall statement and branch coverage”; historical accepted evidence used
the combined metric. Separate ≥80% branch coverage is not demonstrated. Denys must explicitly
resolve the gate semantics; do not edit the canonical threshold or retroactively revoke acceptance
from this record. The current pytest command/configuration has no fail-under enforcement.
Exit 0 proves the assertions passed, not automatic satisfaction of every manual acceptance gate.

Risk-focused test-preparation candidates: `app/cron.py` (0% combined),
`services/background_job_handlers.py` (52%), `services/final_exam_attempts.py` (54%),
and `services/final_exam_answers.py` (63%). These numbers identify missing execution evidence,
not proven production bugs. A separate bounded test scope must choose concrete negative,
cleanup, lease, resume/expiry and device-ownership scenarios from the current contracts.
Do not add assertion-free tests merely to increase coverage.

## Commands actually run

Use the exact environment procedure in [the Harness](../../.harness/TESTING.md).
From backend, `python` below was the existing `..\.venv\Scripts\python.exe`, with RTK:

```text
python -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing --tb=no
python -m ruff format --check .
python -m ruff check .
python -m mypy app tests
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current --check-heads
python -m alembic -c alembic.ini check
```

Frontend: `rtk pnpm format:check`, `lint`, `typecheck`, `test`, `build`, `test:e2e`;
`rtk proxy node --test deployment-artifacts.test.mjs ../.railway/topology.test.mjs`.
Railway topology: `rtk npm run check` from `.railway/`.
Additional read-only checks: runtime OpenAPI (120 paths, 134 operations), coverage data,
Git refs/worktrees/inventory, and Railway status with exact project/environment IDs.

## Reconciliation findings

- Main has no unpublished commits. Existing dirty work is documentation plus a metadata-only
  `question_generation.py` mark; `Photos/` and `outputs/` remain protected and untracked.
- README/STATUS/CONTEXT/Harness and Linear navigation lagged behind published CRA-124, working
  browser SQL, existing NOLOGIN roles and approved sender/budget. The current follow-up reconciles
  those facts while retaining dated history.
- CRA-123 and CRA-124 code is published; their In Progress status is not missing implementation.
  Formal acceptance disposition remains distinct from publication and live staging acceptance.
- FINAL API originally names `GET /organizations/{org_id}/dashboard` and
  `POST /auth/logout-all`; runtime OpenAPI has neither. Broader analytics was excluded from
  bounded slices, but a final implement/defer/superseded disposition was not found. Denys owns
  that product-scope decision; do not synthesize UI/backend behavior from this audit.
- Some historical RED evidence cites missing imports or “No tests found”. Harness requires
  failing behavior assertions. Preserve the record, flag the limitation and never invent old RED.
- No tracked GitHub Actions workflow exists. GitHub protection/settings were not audited.
- Local Playwright uses mock API routes; backend synthetic acceptance prepares part of its data
  directly. Neither is a complete live provider/browser journey.
- S3 signing and Resend adapter tests do not prove real-origin CORS/upload/download or email receipt.
- Load, PITR/restore, real Bacara content, physical accessibility/venue UAT and production smoke
  remain external gates. No full security scan was performed.

## Ordered documentation checkpoint map

1. `docs(project): reconcile published implementation and audit evidence`:
   README.md, STATUS.md, CONTEXT.md, .harness/GIT-WORKFLOW.md, .harness/TESTING.md,
   docs/testing/README.md, docs/testing/caddy-delivery-cra-123.md, this evidence record.
   Verify refs, dates, source hierarchy, links, safe content and exact diff.
2. `docs(deploy): reconcile CRA-122 staging execution and acceptance plan`:
   docs/deployment/staging-cra-122.md and docs/deployment/staging-acceptance-cra-122.md.
   Verify candidate/config names, nine roles, grants/secret boundaries, existing approvals,
   live acceptance matrix and rollback; mirror the current state in Linear.

This expands the prior proposed first boundary by one durable evidence file so the measured
coverage and audit findings are available from the repository rather than a local chat artifact.
Documentation-only TDD exception: no runtime behavior changed. No local commit or push is
authorized by this map; preserve the index and existing user changes.

## Documentation synchronization verification — 2026-09-07

The authorized follow-up updated ten repository documents and six Linear resources (START HERE,
project description, CRA-122, Stage 2 document, CRA-123 and CRA-124). Six readbacks confirmed the
current September 7 checkpoint, published e18af71 and coverage metrics; issue states were preserved.
All 33 live acceptance case IDs were preserved.

Documentation checks: 102 local links checked, zero broken; focused sensitive-value/local-path
pattern scan had zero matches; no stale SHA/sender/storage-fix wording remains in the active
Stage 2 plan. Dated history is explicitly separated. `git diff --check` passed. Application-code
diff and staged diff are empty; the pre-existing metadata-only mark is preserved.
No application tests were rerun for the documentation-only change. The 552/72/42/5 test results
remain the earlier September 7 audit, not new synchronization evidence. Local commits, push,
provider configuration and deployment were not performed.

## Accepted coverage decision and next implementation boundary

Denys approved independent overall gates of at least 80% statements and at least 80% branches
on September 7. Statements PASS; branches FAIL. The critical aggregate gate remains unchanged.
The [bounded closure plan](coverage-closure-plan.md) records exact counts, scenarios, expected
paths, verification and seven proposed commit boundaries. Preparing it does not authorize
implementation or commits. Historical audit and acceptance evidence above remain unchanged.

Dashboard/logout-all disposition, formal CRA-123/124 acceptance and Stage 2 approval remain
separate decisions. No application tests were rerun for this decision/planning update.
