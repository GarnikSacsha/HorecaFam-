# Backend coverage closure plan — 2026-09-07

## Latest Git checkpoint — authorized local commit map

Denys explicitly authorized all ten selective local commits. Checkpoints 1–9 have been created
on local `main`, after their mapped tests, Ruff format/check, strict mypy, exact diff review and
staged-inventory/blob verification. This final documentation checkpoint records that evidence.
The older uncommitted/commit-approval-pending wording below is historical. No push, PR, merge,
history rewrite, provider action or deployment occurred. Linear retains the previously published
809-test result; this local Git step does not silently change issue acceptance or external records.

| Checkpoint | Local commit | Focused pytest passed | Seconds | Ruff/mypy Python paths |
| --- | --- | ---: | ---: | ---: |
| 1. Independent gates | d24e7a2 | 16 | 0.22 | 2 |
| 2. Menu PATCH correction | 5be06c1 | 85 | 130.04 | 2 |
| 3. Menu coverage | ff062a9 | 81 | 131.91 | 4 |
| 4. Training coverage | a42712a | 92 | 221.94 | 6 |
| 5. Assessment coverage | e79d30c | 69 | 228.72 | 4 |
| 6. Admin cursor correction | 18f7199 | 17 | 60.33 | 2 |
| 7. Employee retake correction | 25f57e2 | 5 | 16.56 | 2 |
| 8. Retake clock coverage | d6d9485 | 28 | 90.45 | 1 |
| 9. Operations coverage | b9a66e8 | 119 | 314.41 | 9 |

Each focused run had 0 failed and 0 skipped tests; all listed Ruff/mypy checks passed. These are
separate, overlapping suites and must not be summed as unique tests. Commands used the guarded
Harness test environment and `python -m pytest -q -p no:cacheprovider <mapped files> --tb=no`.
The per-checkpoint file lists below define each run; checkpoint 2 additionally included
`tests/api/test_menu_admin_api.py`. Ruff format/check and mypy used that checkpoint's exact
changed Python paths. Checks ran in the unchanged approved working tree; this is not a claim
of nine isolated full-suite runs at each intermediate commit.

After checkpoint 9, the 217-source hash still equals the full 809-pass acceptance run's hash.
All 32 mapped app/test paths are now committed; no new application behavior was introduced
during Git execution. The existing full report remains the complete regression/coverage evidence.
The next safe action is review of the resulting local range, followed by separately authorized
publication and an exact CRA-122 staging candidate decision.

Final documentation verification: exactly five staged documents match the approved whole-file
or selective-content boundaries; 58 relative links resolve in the staged Git tree, with 0
broken targets. Every committed app/test Python file matches the verified working source;
no private-key header or absolute local path was found in the staged additions. The saved
full-report gate was reevaluated and all three raw-count gates passed unchanged. The Git patch
SHA-256 was independently verified before commit. A temporary-file permission failure and an
unavailable PowerShell hashing command were setup-only; elevated temporary-file access and the
Python hash/content check completed successfully. No application source changed during this step.

## Current result — CRA-125 local gates passed

One fresh complete PostgreSQL 16 run passed **809 tests, 0 failed, 0 skipped in 1984.30s**
on Python 3.12.10. The independent gate helper exited 0:

| Metric | Covered / total | Result |
| --- | --- | --- |
| Overall statements | 11408 / 12135 | 94.01% — PASS |
| Overall branch destinations | 2041 / 2538 | 80.42% — PASS |
| Fixed nine-file critical aggregate | 1293 / 1443 | 89.60% — PASS |

All application Python files are present in the report; raw integer comparisons determine
the result before rounding. Thresholds and critical file membership are unchanged. No source
omission, no-cover pragma, skip/xfail or stale coverage merge was introduced. The branch gate
requires 2031 destinations at this denominator; the measured result is 10 above that minimum.

Evidence is ignored local runtime output under `backend/.pytest_cache/cra125/full-acceptance-1/`:
`current.coverage`, `current.json`, `pytest.log`, and a dedicated fresh `tmp/` directory.
After loading the guarded test environment from `.harness/TESTING.md`, the run used
`COVERAGE_FILE=.pytest_cache/cra125/full-acceptance-1/current.coverage` and this command from backend:

```powershell
rtk proxy ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --basetemp=.pytest_cache/cra125/full-acceptance-1/tmp --cov=app --cov-branch --cov-report=json:.pytest_cache/cra125/full-acceptance-1/current.json --tb=no
rtk proxy ..\.venv\Scripts\python.exe -m tests.coverage_gate .pytest_cache/cra125/full-acceptance-1/current.json
```

Ruff format check passed for 238 files; Ruff check passed; strict mypy passed for 217 source
files. The aggregate SHA-256 of the 217 app/test Python sources matched before and after the
full run: `f03951b6cbba86b634450917667532f6a0bca50d93985adaaf3162d1b50af54a`.
All three separately authorized production corrections are GREEN. Public response schemas,
RBAC, database schema and provider contracts are unchanged. Local implementation and verification
are complete and ready for Denys's acceptance; this is not staging acceptance or commit approval.

Next steps in order: accept the reviewed CRA-125 result and authorize its selective local commit
map; then separately approve any push and the exact CRA-122 Stage 2 provider/settings step.
The seven checkpoint boundaries and three corrective boundaries below remain uncommitted.
Stage 2 still requires scoped configuration/DB preparation, deployment and live acceptance;
the local gate does not perform those actions.

Final local review: `git diff --check` passed; 57 local documentation links resolve, with
0 missing targets; no added skip/xfail/no-cover markers or private-key headers were found
in the reviewed app/test diff. The Git index remains empty and protected user files remain
outside the change map.

### Final Linear synchronization completed — 2026-09-07

After the earlier automatic approval rejection, Denys explicitly authorized the exact payload
and all four destinations. The summary below was published to CRA-125, CRA-122, START HERE and
the accepted coverage-plan document at 14:46–14:47 UTC. Independent readback verified the complete
summary in all four records. The synchronization blocker is resolved; earlier records remain
intact. Both issues retain In Progress status pending their respective acceptance.

Published concise payload for CRA-125, CRA-122, START HERE and the accepted coverage-plan document:

> CRA-125 local implementation and verification are complete and ready for acceptance.
> One fresh full PostgreSQL 16 run: 809 passed, 0 failed, 0 skipped in 1984.30s.
> Independent gates pass: statements 11408/12135 (94.01%), branches 2041/2538 (80.42%),
> unchanged nine-file critical aggregate 1293/1443 (89.60%). Ruff format/check and strict
> mypy pass. All three approved corrections are verified. Thresholds and source inventory
> are unchanged; no stale coverage was merged. No commit, push or deployment occurred.
> Previous failed-gate/correction-pending records are historical. CRA-125 awaits acceptance;
> CRA-122 Stage 2 remains separate and open.

Next immediate step is local acceptance and selective commit-map review, followed by separately
scoped Stage 2 work. This synchronization did not change application code or execute tests,
commits, push or deployment.

## Completed continuation — retake-action correction authorized and GREEN

Denys explicitly authorized the target-Assessment correction and continued CRA-125 coverage
closure. The historical pending-correction statements below are superseded. The agreed atomic
boundary remains uncommitted; commit, push and deployment are not authorized.

Fresh RED before app changes: 2 failed, 1 passed, zero skipped in 8.95s. Unrelated Interactive
and Practice Attempts incorrectly selected `resume_retake` for a Final Exam Requirement.
`employee_follow_up.py` now joins AssessmentVersion and filters its stable Assessment ID against
the Requirement target. The existing Employee/Training scope and response schema are preserved.
Four mapped follow-up files passed 28 tests, zero failed/skipped in 88.25s, including matching
Final Exam resume, frozen `wait` and cancelled `review_history`.

Additional focused evidence:

- Fresh refinement-3 coverage run: 95 passed, zero failed/skipped in 293.66s. It adds 146
  previously missing destinations in unchanged app files; the changed Employee follow-up file
  is excluded from this diagnostic comparison. No historical data was merged into acceptance.
- MFA challenge rejection, Employee history pagination and final/practice prerequisites:
  20 passed, zero failed/skipped in 66.02s.
- Final Exam and Practice takeover: 8 passed, zero failed/skipped in 20.15s; rejected attempts
  retain their lease, and successful replay increments generation only once.
- Final Exam resume/readback/finish scenario: 1 passed, zero failed/skipped in 3.82s; resume
  preserves the attempt and saved answers remain free of grading feedback before completion.
- Ruff format check: 238 files; Ruff check passed; mypy passed for 217 source files;
  `git diff --check` passed.

The fresh full acceptance run completed with 809 passing tests and all three gates passing,
as recorded above, using isolated evidence under `.pytest_cache/cra125/full-acceptance-1`.
No production paths other than the three explicitly approved corrections have changed.

Separated review: the new join uses the Attempt's AssessmentVersion primary key and retains
the existing Employee and Training predicates. It only selects an ID for a public action;
there is no write, migration, response-field change or authorization expansion. The exact app
diff contains only `menus.py`, `admin_follow_up.py` and `employee_follow_up.py`. All 26 changed
tracked test files remain inside the approved map; three new helper/unit files are also mapped.
The Git index is empty. The original documentation changes, metadata-only
`question_generation.py` mark, `Photos/` and `outputs/` remain outside selective staging.

## Earlier checkpoint — full gate measured; new defect required a bounded correction

The previously approved menu PATCH and Admin cursor fixes are implemented and verified.
The following full run is newer than the original 552-test audit, but predates the final
refinement tests and their newly discovered RED case.

| Evidence | Actual result |
| --- | --- |
| Fresh full PostgreSQL 16 suite | 711 passed, 0 failed, 0 skipped; 1606.36s |
| Independent statement gate | 11104/12135 = 91.50% — PASS |
| Independent branch gate | 1860/2538 = 73.29% — FAIL |
| Fixed nine-file critical aggregate | 1241/1443 = 86.00% — PASS |
| Refinement 1 | 25 passed, 0 failed, 0 skipped; 66.54s |
| Refinement 2, including refinement 1 | 65 passed, 0 failed, 0 skipped; 197.34s |
| Later publication and assignment cases | 16 passed, 0 failed, 0 skipped; 71.52s |
| New follow-up reproduction plus three validation cases | 4 passed, 1 intended failed, 0 skipped; 10.63s |
| Complete employee follow-up file, independent rerun | 3 passed, 1 intended failed, 0 skipped; 9.63s |
| Ruff check / strict mypy | Passed; mypy checked 217 source files |

Ignored local evidence directories under backend: `.pytest_cache/cra125/full-20260907-1120`,
`.pytest_cache/cra125/refinement-1`, and `.pytest_cache/cra125/refinement-2`.
Each has its own fresh coverage data and JSON. No stale coverage was merged.
Refinement 2 executed 97 branch destinations missing from the full run, leaving 74 to the
80% threshold on the same application sources. This intersection is only a planning
diagnostic; it is not a current full-run percentage or acceptance result. Later passing
publication/assignment cases are not included in that gain.

The refinements cover malformed and terminal administrative actions, MFA recovery rejection,
worker shutdown and polling, practice prerequisites, employee lifecycle replay, revoked and
expired assessment write guards, retake clock boundaries, invalid training targets and
publication dependencies/translations. Database constraints rejected several initially invalid
fixtures (expiry equal to start, duplicate stable code, unknown asset state); those fixtures
were corrected without app changes. Schema construction and endpoint parameter mistakes were
also corrected before the passing results above.

### New production defect and proposed corrective map

Canonical source: [CRA-69](https://linear.app/craftspacee/issue/CRA-69) and the accepted Slice 8
override in [FINAL CRA-12](https://linear.app/craftspacee/document/rest-api-contract-horeca-training-platform-v01-final-cra-12-e022ee303ee4).
Requirements have a stable target Assessment and expose the permitted action for that retake.

Reproduction: an Active management Requirement targets the Final Exam. The same Employee has
one in-progress Interactive Training Attempt in the same Training and Assignment, but no
Final Exam Attempt. `GET /api/v1/me/training/retake-requirements` returns
`permitted_action=resume_retake` instead of `start_retake`. The paired matching Final Exam
case passes. This is a misleading Employee action, not a demonstrated authorization bypass.

Cause: `employee_requirement_response` in `backend/app/services/employee_follow_up.py`
looks for any in-progress Attempt with the same Employee and Training; it does not constrain
the Attempt's Assessment Version to `requirement.target_assessment_id`.

The real PostgreSQL API regression is retained without skip/xfail:
`test_retake_resume_action_requires_a_matching_assessment[interactive-start_retake]`.
The independent rerun fails exactly on `'resume_retake' == 'start_retake'`.
The production file has not been edited.

Ordered corrective boundary pending Denys authorization:

1. Filter the active-Attempt query through AssessmentVersion and the Requirement's stable
   target Assessment. Preserve the response schema and existing frozen/history behavior.
   Expected production path: `backend/app/services/employee_follow_up.py`.
2. Retain the paired API regression in `backend/tests/api/test_employee_follow_up_api.py`.
   Verify unrelated Interactive/Practice Attempts cannot supply a Final Exam resume action,
   matching Final Exam Attempts still can, and frozen/terminal responses remain correct.
   Run the four mapped follow-up files, Ruff format/check, mypy and inspect the exact diff.
3. Record GREEN in this document, STATUS and CRA-125; continue the remaining mapped coverage
   work and obtain one new complete full-suite report with all independent gates passing.

One intended atomic outcome: `fix(follow-up): match resume action to requirement assessment`.
This would extend the approved production map by the one file above. No local commit, push,
deployment, provider execution, dependency or migration is authorized. CRA-125 explicitly
requires: "Stop and report any production defect requiring app changes or scope expansion."
It remains In Progress, with acceptance pending this bounded correction and the final gates.

## Earlier checkpoint — cursor correction authorized and verified

Denys explicitly approved the cursor correction, continued CRA-125 implementation and Linear
synchronization. Historical approval pauses and the earlier external-write rejection below
are superseded. No commit, push or deployment authorization was added.

Fresh RED: 4 failed, 11 deselected, zero passed/skipped in 12.01s. Each Admin list returned 500
for a naive timestamp with rows and 200 for the same invalid timestamp with no rows.
Added an offset guard before iteration in both list functions in
`backend/app/services/admin_follow_up.py`. Extended the existing mapped API test with empty-list
rejection and successful next-page traversal using the server cursor. The four mapped follow-up
files passed **23 tests, zero failed/skipped in 61.03s**. Separate diff review confirms guards
precede comparison and preserve filtering, sorting, RBAC and existing INVALID_CURSOR envelopes.
The corrective boundary remains one uncommitted checkpoint with its tests and evidence.

Linear CRA-125 now contains the approved continuation, prior menu/training/assessment results
and fresh cursor RED/GREEN evidence; the successful update response was read back.
Checkpoint 6 is in progress: cron transaction/disposal/error redaction tests (11 passed),
maintenance validation/recovery/retention and malformed worker payload cases. The first cron
run lacked the fixture's required database_url (setup-only); corrected with an unused synthetic
test URL. A missing-attempt recovery fixture initially attempted to delete append-only history;
the database correctly rejected that setup. The fixture now creates the orphan processing job
directly and preserves immutable history. These were fixture corrections, not production bugs.
No fresh full coverage gate is claimed yet.

## Historical continuation — cursor defect and corrective proposal

The menu PATCH correction below is verified. Subsequent CRA-125 test additions cover:

- Menu import staleness, unresolved findings, missing findings and publication blockers.
  Import/publication files: 15 passed, zero failed/skipped in 62.40s.
- Training video/list validation, failed asset completion, tenant-scoped asset archive,
  rejected lesson creation and publication blockers without new assignments/jobs.
  Schema/assets: 40 passed, zero failed/skipped in 29.94s. Draft/publication/assignment/rollout:
  initially 32 passed and one setup failure in 95.64s because a deliberately blank translation
  title violated the database constraint before reaching readiness. The fixture now uses the
  valid persisted `stale` translation state; the complete publication file then passed eight
  tests in 33.86s. No production correction was needed for these training scenarios.
- Final Exam and Interactive start prerequisites, with no new attempts/results/audit on
  rejection. Final Exam's four new prerequisite cases passed in 9.97s (one deselected).
- Admin Attention and Retake Requirements malformed cursor validation. Four malformed forms
  are controlled; a timezone-less timestamp is parsed successfully, then compared with an
  aware database timestamp outside the validation exception handler. This raises TypeError
  and returns HTTP 500 instead of the established 422 INVALID_CURSOR response.

The first Attention reproduction: four passed, one failed, three deselected in 14.21s.
The failing case reaches authenticated listing, obtains a real server cursor, alters only
its timestamp while preserving the filter fingerprint, and proves the first page remains
unchanged after rejection. The same regression now covers both Admin list endpoints.
The failure is preserved without skip/xfail; admin_follow_up.py has not been edited.

Final focused PostgreSQL run: **31 passed, 2 failed, 0 skipped/deselected in 94.97s**.
Both failures are the expected timezone-less cursor regressions, one per Admin list.
All 20 tests in the five mapped assessment files and the other 11 Attention cases passed.
After loading the guarded test environment from `.harness/TESTING.md`, run from `backend/`:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/api/test_attention_admin_api.py tests/integration/test_final_exam_service.py tests/integration/test_interactive_attempt_service.py tests/integration/test_interactive_answer_service.py tests/integration/test_interactive_history_service.py tests/integration/test_practice_attempt_service.py --tb=no
```

Required next corrective boundary, pending Denys approval:

1. In `backend/app/services/admin_follow_up.py`, validate that the parsed cursor datetime
   includes an offset before either list comparison, returning existing INVALID_CURSOR for
   invalid input even if the result set is empty. Keep filtering, sorting, RBAC and error
   envelopes unchanged; no broad exception catch or new dependency.
2. In `backend/tests/api/test_attention_admin_api.py`, retain both RED cases, add an empty-list
   case and verify a valid server-issued cursor still retrieves its next page. Run the four
   mapped follow-up files plus Ruff format/check and strict mypy; review rejection placement.
3. Update this record and STATUS.md with GREEN evidence. Proposed eventual atomic boundary:
   `fix(follow-up): reject cursors without timezone offsets`. Local commit is not authorized.

CRA-125 explicitly says: "Stop and report any production defect requiring app changes or
scope expansion." Checkpoint 6 and full coverage acceptance therefore remain pending.
No current coverage percentages or completed checkpoint 2–5 coverage gains are claimed;
fresh focused arc evidence and the final full gate are still required.

Backend-wide verification: Ruff check passed; Ruff format check reported 237 files formatted;
strict mypy passed with 216 source files. Reviewed diffs and git diff --check passed, with only
Git's existing LF/CRLF notices. The index is empty. Original dirty documentation/assets remain.
No dependency, migration, frontend, provider, commit, push or deployment action was performed.

Automatic approval review rejected the attempted external CRA-125 description update because
explicit Linear-write authorization was absent. Nothing was written to Linear. The reviewable
sync payload is the menu correction evidence plus this continuation, exact test results and
the pending cursor correction; publishing it requires explicit authorization.

### Files changed during this continuation

- `backend/app/services/menus.py`
- `backend/tests/integration/test_menu_item_service.py` (extends pre-existing dirty regressions)
- `backend/tests/api/test_menu_import_api.py`
- `backend/tests/api/test_menu_publication_api.py`
- `backend/tests/unit/test_training_schemas.py`
- `backend/tests/integration/test_training_assets.py`
- `backend/tests/integration/test_training_draft_service.py`
- `backend/tests/api/test_training_publication_api.py`
- `backend/tests/integration/test_final_exam_service.py`
- `backend/tests/integration/test_interactive_attempt_service.py`
- `backend/tests/api/test_attention_admin_api.py`
- `STATUS.md` and this execution record (both already local before this continuation)

## Verified corrective checkpoint — merged PATCH

Denys authorized proceeding through the reviewed plan, including the precise corrective
boundary below and continuation of CRA-125. The earlier approval pause is historical.
Only merged MenuItemWrite validation is translated into the existing safe 422 API error;
transaction rollback, tenant checks and unrelated exception handling remain intact.

Fresh RED: 2 failed, 0 passed/skipped, 5 deselected in 8.55s (500 instead of 422).
Focused GREEN: 2 passed, 0 failed/skipped, 5 deselected in 7.28s, including unchanged data,
revision and audit after rejection and one successful subsequent PATCH.
Complete item/draft/schema/Admin/import/publication suite: 69 passed, 0 failed/skipped in
85.40s. Ruff format/check passed. Strict mypy from backend passed after narrowing test values;
an initial root-directory invocation lacked the backend configuration and was corrected.
Separate review confirms catch scope and safe error shape; no global validation catch.

Corrective boundary: backend/app/services/menus.py,
backend/tests/integration/test_menu_item_service.py and this execution record.
Intended checkpoint: `fix(menu): return validation error for invalid merged item patches`.
No commit, push or provider operation. Subsequent work reached the cursor stop recorded above;
no new full-suite coverage pass is claimed.

## Historical checkpoint — initial menu defect pause — 2026-09-07

Denys authorized the seven-checkpoint coverage plan and creation of [CRA-125](https://linear.app/craftspacee/issue/CRA-125/close-independent-backend-statement-and-branch-coverage-gates). This supersedes the pending implementation-approval wording in the dated planning record below. Commits and external actions remain unauthorized.

Checkpoint 1 is implemented locally: gate helper plus 16 passing unit tests. Menu schema/draft tests: 49 passed, zero failed/skipped. Two subsequent item-PATCH regression cases confirm HTTP 500 instead of controlled 422 on invalid merged state; data/revision/audit rollback checks pass. Five changed Python files pass Ruff format/check and strict mypy. Per the approved stop condition, app code is unchanged and CRA-125 pauses for approval of the precise correction recorded in the issue. Two regression cases remain failing, not skipped. Checkpoints 3–7 and a fresh full coverage gate are not complete. CRA-122 staging Stage 2 remains separate and open.

## Status and authority

Planning draft v1 under CRA-122; implementation is not started. Denys approved the
two independent overall thresholds and preparation of this plan on September 7.
Canonical decision: [CRA-13](https://linear.app/craftspacee/issue/CRA-13/define-backend-test-strategy-and-vertical-slice-acceptance-criteria).
Read [START HERE](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974)
and the latest accepted slice closures before implementing each family.

The next implementation needs one separately bounded Linear issue accepting this map.
No new product behavior, endpoints, dependencies, architecture, provider calls, deployment,
commit or push is authorized by this planning document. Preserve the existing dirty
documentation, Photos, outputs and question_generation.py metadata mark.

## Baseline and exit criteria

Source: published main `e18af71f89d587b1cb6b472cf189e67dfa8102a0`.
The [September 7 audit](repository-audit-2026-09-07.md) ran 552 backend tests:
552 passed, zero failed, zero skipped. Its existing coverage data was inspected for this plan.

| Metric | Covered / total | Exact-count gate | Current result |
|---|---:|---|---|
| Overall statements | 10820 / 12127 | At least 80% | 89.22%, PASS |
| Overall branch destinations | 1717 / 2534 | At least 80% | 67.76%, FAIL |
| CRA-77 critical aggregate | 1172 / 1443 | At least 80% | 81.22%, PASS |

The critical set remains the accepted nine files: services/password_recovery.py,
mfa_enrollment.py, employees.py, background_jobs.py, background_job_handlers.py,
maintenance.py, operator_jobs.py; core/observability.py; operations/bootstrap_venue.py,
all below backend/app. No new separate critical branch gate is introduced.

At the unchanged denominator, 2028 covered branch destinations are required: at least
311 additional destinations, leaving at most 506 missing. This is not a count of tests.
Any source/configuration change requires recalculating the denominator. Do not exclude files,
disable branch tracking, remove guards, or add no-cover pragmas to manufacture a pass.

Final acceptance: both overall gates and the critical aggregate pass on one fresh full
PostgreSQL 16 run, zero failed/required-skipped tests, no loss of accepted scenarios,
Ruff format/check and strict mypy pass, exact counts and commands recorded.
Keep the current coverage data intact during focused runs; use separate ignored/temporary
coverage output. Never combine stale results from different source revisions.

## Test design and evidence

Existing tests already exercise many happy paths and some negative cases. The inventory below
is a prioritization of missing destinations, not a claim that every named scenario is absent.
Before adding a case, match its missing arc to an accepted invariant and search existing tests.
Assert response/error, persisted state and absence of forbidden side effects; do not merely
execute a branch. Use real PostgreSQL for transactions, tenancy and concurrency; fake only
external provider boundaries. Use controlled clocks, independent sessions and deterministic
coordination instead of timing sleeps.

For new gate-tool behavior, use RED → GREEN → REFACTOR. Coverage expansion of already-correct
behavior may pass immediately; record the baseline missing arc and subsequent coverage gain,
without inventing a failing test. If a test exposes a production defect, preserve the failing
evidence and open a separately scoped correction before changing app code.

## Ordered implementation checkpoint and commit map

Each checkpoint below is one coherent eventual selective commit. Commit authorization remains
separate; until granted, preserve the same reviewed boundaries without changing the Git index.
Expected paths below are explicit test files, not permission to stage entire directories.

### 1. Make both coverage gates executable

Proposed new paths: `backend/tests/coverage_gate.py` and
`backend/tests/unit/test_coverage_gate.py`; command documentation in
[TESTING.md](../../.harness/TESTING.md). No existing gate helper was found.

Consume a freshly generated coverage JSON report using the installed coverage package and
Python standard library. Require branch data, nonzero totals, valid count ranges and the full
configured app source inventory; require all nine critical files. Evaluate integer comparisons
`100 * covered >= 80 * total` independently, with a separate aggregate calculation for the
fixed critical set. Print counts and each result; return nonzero if a required gate fails.
Do not use `--cov-fail-under=80` alone: it evaluates the combined percentage.

Unit cases: exactly 80 passes; values just below 80 fail despite display rounding; statements
pass/branches fail and vice versa; both pass; missing/malformed report, missing branch mode,
missing critical file and incomplete source inventory fail. The September 7 report must yield
statement PASS / branch FAIL / critical aggregate PASS. That is expected baseline gate output,
not a regression in application behavior.

Focused command, from backend after implementation:
`rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider tests/unit/test_coverage_gate.py`.
Intended commit: `test(coverage): enforce independent statement and branch gates`.

### 2. Menu validation and mutation boundaries

Missing destinations in priority sources: schemas/menu.py 45, services/menu_drafts.py 46,
menus.py 31, menu_imports.py 17, menu_publication.py 10: 149 available to investigate.

Expected edits: `backend/tests/unit/test_menu_schemas.py`,
`backend/tests/integration/test_menu_draft_service.py`,
`backend/tests/integration/test_menu_item_service.py`,
`backend/tests/api/test_menu_import_api.py`,
`backend/tests/api/test_menu_publication_api.py`.

Candidate scenarios: omitted versus explicit null fields; normalized duplicate codes/IDs;
inconsistent unknown/confirmed fact lists; empty/partial patch; invalid position or incomplete
reorder; stale revision; wrong tenant/location/source version; copied hierarchy identity
preservation; rejected mutation leaves revision/audit/data unchanged; stale import resolution
and publish dependency conflicts. Existing draft tests already cover several of these:
extend uncovered variants instead of duplicating them.
Intended commit: `test(menu): cover validation and mutation rejection boundaries`.

### 3. Training publication and assignment boundaries

Priority missing destinations: training_drafts.py 29, training_publication.py 24,
training_rollouts.py 20, training_assignments.py 15, training_assets.py 11,
schemas/training.py 11: 110 to investigate.

Expected edits: `backend/tests/integration/test_training_draft_service.py`,
`backend/tests/integration/test_training_assets.py`,
`backend/tests/integration/test_training_assignment_service.py`,
`backend/tests/unit/test_training_schemas.py`,
`backend/tests/api/test_training_publication_api.py`,
`backend/tests/api/test_training_rollout_api.py`.

Candidate scenarios: no audience/required lessons; stale published-menu dependency or base
version; unready private asset; immutable published draft; replay versus conflicting rollout;
wrong tenant/location assignment and lifecycle revalidation. Assert blocked publication does
not create assignments/notifications, and successful replay produces no duplicates.
Intended commit: `test(training): cover readiness and rollout boundary states`.

### 4. Assessment availability, ownership and immutable results

Priority missing destinations: final_exam_attempts.py 41, final_exam_answers.py 13,
final_exam_results.py 12, interactive_attempts.py 22, interactive_answers.py 11,
interactive_history.py 9, practice_attempts.py 17, practice_answers.py 10,
practice_results.py 11: 146 to investigate.

Expected edits: `backend/tests/integration/test_final_exam_service.py`,
`backend/tests/integration/test_interactive_attempt_service.py`,
`backend/tests/integration/test_interactive_answer_service.py`,
`backend/tests/integration/test_interactive_history_service.py`,
`backend/tests/integration/test_practice_attempt_service.py`.

Candidate scenarios: unavailable assignment/readiness; paused participation; certification
with and without active authorization; expired attempts at the exact boundary; lease ownership
and takeover; replay with incompatible request; foreign attempt reads; partial/empty history;
same result after repeated finish. Existing Final Exam integration already covers certification,
authorized summary and missing critical subject; target the remaining branches. Assert rejected
answers/finish/takeover preserve Attempt, Answer, Result and certification records.
Intended commit: `test(assessment): cover availability lease and history boundaries`.

### 5. Attention and Retake filter and lifecycle boundaries

Priority missing destinations: admin_follow_up.py 44, attention.py 26, retakes.py 24,
employee_follow_up.py 11: 105 to investigate.

Expected edits: `backend/tests/api/test_attention_admin_api.py`,
`backend/tests/api/test_employee_follow_up_api.py`,
`backend/tests/integration/test_attention_workflow.py`,
`backend/tests/integration/test_retake_lifecycle.py`.

Candidate scenarios: malformed and filter-mismatched cursors; empty/final/multiple pages and
stable ordering; location/employee/state filters; stale proposed revision; due-time boundary;
invalid target assessment/assignment; cancelled/completed state replays; missing clean-retake
subject; cross-tenant non-enumeration. Assert no leaked admin comments and no unauthorized
history, certification or obligation mutation.
Intended commit: `test(follow-up): cover cursor and lifecycle rejection boundaries`.

### 6. Worker, maintenance and security lifecycle boundaries

Priority missing destinations: maintenance.py 17, background_job_handlers.py 10,
background_jobs.py 6, operator_jobs.py 15, employees.py 21, mfa_enrollment.py 13,
password_recovery.py 4, worker.py 11, cron.py 4: 101 to investigate.

Expected edits: `backend/tests/integration/test_maintenance_jobs.py`,
`backend/tests/integration/test_background_job_handlers.py`,
`backend/tests/integration/test_background_job_runtime.py`,
`backend/tests/unit/test_worker_composition.py`,
`backend/tests/unit/test_cron_composition.py` (new),
`backend/tests/api/test_operations_api.py`,
`backend/tests/api/test_employee_lifecycle.py`,
`backend/tests/api/test_mfa_enrollment_recovery.py`,
`backend/tests/api/test_password_recovery.py`.

Candidate scenarios: each cron dispatch, unknown/malformed or naive timestamp payload,
empty cleanup, retention dry run, exact cutoff, invalid batch and lease bounds, exhausted
recovery, lost-lease finalization, stale lifecycle/token suppression, invalid operator retry,
MFA/recovery rejection without secret exposure. Exercise entry-point composition with fake
runtime dependencies only; never run cleanup against staging or call a real email provider.
Intended commit: `test(operations): cover maintenance and security boundary states`.

### 7. Full gate and evidence closure

The five domain groups contain 611 missing destinations to investigate; not all are independently
reachable or worth a separate test. Measure actual gain after each group. If meaningful reachable
cases in these paths cannot close the 311 gap, report the remainder and propose a revised bounded
map; do not claim the numeric target is guaranteed.

Expected edits: this plan (execution ledger), [audit evidence](repository-audit-2026-09-07.md),
[testing index](README.md), [repository status](../../STATUS.md) and
[TESTING.md](../../.harness/TESTING.md). Synchronize the implementation issue and CRA-122 with
actual evidence; historical audit numbers remain dated.
Intended commit: `docs(testing): record independent coverage gate closure`.

For checkpoints 2–6, run the existing pytest command below with exactly that checkpoint's
listed test files after removing the `backend/` prefix; record the expanded command before
execution. Also run Ruff format/check and mypy on the mapped tests and gate helper.
Do not apply full-app percentage thresholds to a focused partial suite.

## Final commands and stopping rules

Use the secret-safe PostgreSQL test environment procedure in
[TESTING.md](../../.harness/TESTING.md). From backend:

```powershell
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing
```

After the proposed helper exists, generate fresh JSON from that full run and evaluate it:

```powershell
rtk ..\.venv\Scripts\python.exe -m coverage json -o coverage.json
rtk ..\.venv\Scripts\python.exe -m tests.coverage_gate coverage.json
```

Verify report generation succeeds and no stale file can be consumed. Coverage output is local
runtime data and must not be staged. No app/migration/frontend change is planned; their earlier
audit results are not fresh evidence from this documentation step. Any later release gate still
uses the complete applicable Harness commands and live acceptance stages.

Stop for a production defect requiring app edits, a canonical contradiction, dependency or
architecture change, non-test database/provider action, or proposed scope expansion.
Neither passing this plan's future gate nor the current approval authorizes Stage 3 deployment
settings, migrations, sends, commits or publication.

## Planning verification — 2026-09-07

Documentation-only verification checked nine current documents and 115 relative links: zero
broken links, zero matches in the focused sensitive-value/local-path pattern scan, and no
superseded pending-gate wording in current sections. All 31 mapped test/helper paths were
checked: existing paths resolve; three new paths are explicitly proposed. All 33 staging
acceptance case IDs remain present. Eight Linear readbacks confirmed the approved decision
and plan navigation; issue states were preserved. git diff --check passed; application-code
and staged diffs remain empty. No application tests were rerun. No commits or provider actions
were performed. This verifies the planning artifact, not its future coverage target.

## CRA-125 execution ledger — 2026-09-07

Authorization: Denys approved issue creation and plan execution; CRA-125 is In Progress.
No local commit, push, provider or production-code modification is authorized by that approval.

1. Coverage helper: 16 intended RED failures against a stub, then 16 passed / 0 failed / 0
   skipped in 0.23s. Initial temporary-directory permission errors were setup-only.
   Command from backend: `rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider tests/unit/test_coverage_gate.py --tb=short`.
   Baseline helper output: 10820/12127 statements PASS, 1717/2534 branches FAIL,
   1172/1443 critical aggregate PASS; expected exit 1.
2. Menu schema and draft mutation tests: 49 passed / 0 failed / 0 skipped in 29.33s.
   Command: `rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider tests/integration/test_menu_draft_service.py tests/unit/test_menu_schemas.py --cov=app --cov-branch --cov-report= --tb=short`.
   Dedicated PostgreSQL 16 environment loaded using Harness instructions without printing values.
   Separate `COVERAGE_FILE=.pytest_cache/cra125/menu.coverage` preserved the full audit.
   Comparison of baseline missing arcs with this run's executed arcs finds **65 additional
   destinations**: schemas/menu.py 42; services/menu_drafts.py 23. This is partial-run evidence,
   not a newly accepted full coverage percentage.
3. Item PATCH regression: 0 passed / 2 failed / 0 skipped, 5 deselected in 6.75s.
   Command: `rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider tests/integration/test_menu_item_service.py -k invalid_merged --tb=short`.
   Both authenticated requests return 500 rather than 422. Inputs: name_uk=null; or
   component_data_status=confirmed_present while the current component list remains empty.
   Setup, subsequent reads, unchanged Item response, Draft revision and AuditEvent count
   all pass. The failure is an unhandled merged-model Pydantic ValidationError, not test setup.
4. Ruff format/check and strict mypy pass for all five changed Python files. Full regression
   and checkpoints 3–7 have not run. Failing regression cases remain visible, with no xfail.

### Corrective boundary ready for approval

One focused correction is proposed in `backend/app/services/menus.py`: catch Pydantic
ValidationError only around merged MenuItemWrite validation and raise the existing generic
422 VALIDATION_ERROR. Keep transaction rollback and do not globally catch validation errors,
which could conceal response/programming defects. Reuse the two failing tests and add a valid
subsequent PATCH to prove recovery.

Expected corrective paths: `backend/app/services/menus.py`,
`backend/tests/integration/test_menu_item_service.py`, this evidence document.
Verification: focused item regression → complete item/draft/schema/menu API tests → Ruff/mypy
and a separate review of exception scope, tenant boundaries, rollback and error redaction.
Intended single commit boundary: `fix(menu): return validation error for invalid merged item patches`.
Commit permission remains separate. Obtain the bounded corrective issue/implementation approval
before app edits, then resume the already-authorized CRA-125 coverage map.

### Historical first-checkpoint staging proposal (superseded)

Checkpoint 1: backend/tests/coverage_gate.py, backend/tests/unit/test_coverage_gate.py and only
the corresponding CRA-125 command/evidence hunks in .harness/TESTING.md.
Checkpoint 2 partial: backend/tests/unit/test_menu_schemas.py and
backend/tests/integration/test_menu_draft_service.py; mapped remaining menu paths are unfinished.
The two failing cases in backend/tests/integration/test_menu_item_service.py are RED evidence,
not a commit-ready checkpoint. Status and this plan are documentation of incomplete execution.
Preserve all earlier user/audit documentation hunks and the metadata-only question_generation.py
mark, Photos and outputs; no Git index changes were made.

## Final selective commit map prepared — 2026-09-07

This is the reviewable next local Git step, not executed commits. It refines the original seven
checkpoints with the three explicitly approved corrective boundaries. Corrective API files stay
whole with their fixes because they also contain related pagination/rejection coverage; they are
not staged again in the general follow-up checkpoint. Unchanged mapped files are verification
inputs only. Command documentation and the final evidence ledger are consolidated in checkpoint
10 so they describe the completed range. No failing RED state is a proposed commit.

The map contains 32 unique app/test paths: three production files, 26 changed tracked test files
and three new helper/unit files. Each path below means its complete reviewed CRA-125 diff; this
includes the already-present mapped menu regression additions, not unrelated documentation.
Apply checkpoints in order. Checkpoints 3 and 8 depend on the earlier corrections; checkpoint 10
depends on all preceding checkpoints. No tests require uncommitted later production corrections.
Before every authorized commit, run its focused verification plus Ruff format/check and mypy
for its Python paths, inspect the exact staged diff and run git diff --cached --check. Use the
Harness guarded PostgreSQL environment and existing pytest invocation; never run database suites
concurrently. The current 809-pass full report is evidence for the final tree, not a claim that
these individual intermediate committed trees have already been tested.

### Commit 1: `test(coverage): enforce independent statement and branch gates`

- `backend/tests/coverage_gate.py`
- `backend/tests/unit/test_coverage_gate.py`

Verification: Run all 16 gate unit cases; inspect integer thresholds, source inventory and malformed-report rejection.

### Commit 2: `fix(menu): return validation error for invalid merged item patches`

- `backend/app/services/menus.py`
- `backend/tests/integration/test_menu_item_service.py`

Verification: Run the complete item service file and adjacent menu API/draft/schema files; retain both recorded RED cases and valid next PATCH.

### Commit 3: `test(menu): cover validation and mutation rejection boundaries`

- `backend/tests/unit/test_menu_schemas.py`
- `backend/tests/integration/test_menu_draft_service.py`
- `backend/tests/api/test_menu_import_api.py`
- `backend/tests/api/test_menu_publication_api.py`

Verification: Run these four test files plus the item service file from checkpoint 2.

### Commit 4: `test(training): cover readiness and rollout boundary states`

- `backend/tests/integration/test_training_draft_service.py`
- `backend/tests/integration/test_training_assets.py`
- `backend/tests/integration/test_training_assignment_service.py`
- `backend/tests/unit/test_training_schemas.py`
- `backend/tests/api/test_training_publication_api.py`
- `backend/tests/api/test_training_rollout_api.py`

Verification: Run these six test files.

### Commit 5: `test(assessment): cover availability lease and history boundaries`

- `backend/tests/integration/test_final_exam_service.py`
- `backend/tests/integration/test_interactive_attempt_service.py`
- `backend/tests/integration/test_interactive_history_service.py`
- `backend/tests/integration/test_practice_attempt_service.py`

Verification: Run these four files plus unchanged tests/integration/test_interactive_answer_service.py.

### Commit 6: `fix(follow-up): reject cursors without timezone offsets`

- `backend/app/services/admin_follow_up.py`
- `backend/tests/api/test_attention_admin_api.py`

Verification: Run the Admin Attention API file; include empty-list rejection and valid server-issued pagination.

### Commit 7: `fix(follow-up): match resume action to requirement assessment`

- `backend/app/services/employee_follow_up.py`
- `backend/tests/api/test_employee_follow_up_api.py`

Verification: Run the Employee follow-up API file; include unrelated Interactive/Practice, matching Final Exam, frozen/history and pagination.

### Commit 8: `test(follow-up): cover retake lifecycle boundaries`

- `backend/tests/integration/test_retake_lifecycle.py`

Verification: Run all four mapped follow-up files, including unchanged tests/integration/test_attention_workflow.py.

### Commit 9: `test(operations): cover maintenance and security boundary states`

- `backend/tests/integration/test_maintenance_jobs.py`
- `backend/tests/integration/test_background_job_handlers.py`
- `backend/tests/integration/test_background_job_runtime.py`
- `backend/tests/unit/test_worker_composition.py`
- `backend/tests/unit/test_cron_composition.py`
- `backend/tests/api/test_operations_api.py`
- `backend/tests/api/test_employee_lifecycle.py`
- `backend/tests/api/test_mfa_enrollment_recovery.py`
- `backend/tests/api/test_password_recovery.py`

Verification: Run these nine test files.

### Commit 10: `docs(testing): record independent coverage gate closure`

- `docs/testing/coverage-closure-plan.md`: complete reviewed execution ledger and this map.
- `docs/testing/repository-audit-2026-09-07.md`: complete dated baseline evidence, already named
  by original checkpoint 7 and required by the new coverage documentation links.
- `.harness/TESTING.md`: only the added top sections from `Latest local CRA-125 evidence`
  through the line before `Supported baseline`, and the added report/gate command block
  between `Exact project commands` and `Run from backend/`. Preserve the unrelated Caddy tail.
- `docs/testing/README.md`: only the added top evidence sections before `Canonical test strategy`.
  Preserve the unrelated Caddy publication tail.
- `STATUS.md`: only the CRA-125 active block before `Published main is` and the original-audit
  coverage paragraph that points to the now-passing closure record. Preserve other audit,
  staging and historical reconciliation changes.

These are selective content boundaries, not authorization to stage those three shared files
wholesale. At execution, update only factual commit/acceptance wording after the corresponding
action actually occurs. Verify documentation links against the staged tree, scoped inventory,
exact diff and empty sensitive/runtime inventory. Reconfirm the full-source hash against the
809-pass run; rerun the full gate if Python sources changed. No new full pytest run occurred
during this map preparation.

Excluded from this map: `.harness/GIT-WORKFLOW.md`, `CONTEXT.md`, root `README.md`, all
`docs/deployment/` changes, `docs/testing/caddy-delivery-cra-123.md`, remaining shared-document
hunks, metadata-only `question_generation.py`, `Photos/`, `outputs/`, secrets and test runtime
artifacts. The Git index remains empty until explicit local-commit authorization.

### Following staging preparation

The old proposed artifact `e18af71` does not include CRA-125. A new candidate SHA can be named
only after the local range exists and its publication is separately authorized. Stage 2 must
then reconcile the now-passing local gate with the candidate and finish its remaining decisions:
original Dashboard/logout-all disposition, CRA-123/124 acceptance, DB LOGIN/secret/grant setup,
storage runtime settings and live-origin evidence, email key scope/runtime, service cost limits
and first synthetic operator. These are existing CRA-122 items, not new implementation scope.
The subsequent approved order remains source/settings preparation, one migration, API/worker/
crons, web last, the 33-case live acceptance matrix, then delivery evidence and acceptance.
No provider state was queried or changed during this local map preparation.

Map verification: 32 unique app/test paths, 0 missing files, 0 unmapped Python content changes;
57 local documentation links, 0 broken targets; git diff --check passed and the index is empty.
The 217-source hash still matches the 809-pass full run. An initial inventory script had a
quoting error before its checks; the corrected read-only invocation produced these results.
