# Manual QA corrections — 2026-10-06

Denys authorized correcting the four demonstrated defects after live Admin/Employee QA.
This is the bounded acceptance continuation of CRA-275. Denys subsequently authorized
selective commits and push of these fixes, followed by additional tests. No PR, merge
or deployment is included in that Git authorization.

## Ordered selective commit map (authorized 2026-10-06)

1. `fix(admin): distinguish empty employee searches`: AdminEmployeesPage.tsx and
   AdminFlow.test.tsx; focused search/empty-team tests then the Admin flow suite.
2. `fix(auth): invalidate revoked sessions during navigation`: SessionContext.tsx,
   LoginPage.tsx and SessionGate.test.tsx; 401 redirects, unrelated failures retain
   session, stale request cannot invalidate a new login; auth/session regression.
3. `fix(exams): reopen completed employee answer reviews`: final_exam_results.py,
   assessments.py, test_operations_hardening_acceptance.py, EmployeeFinalExamPage.tsx,
   its unit tests and e2e/final-exam-slice.spec.ts, including the page's timing label.
   Owned completed attempt only; no feedback before finish; read-only endpoint;
   existing immutable review serializer. Real PostgreSQL and frontend regression.
4. `fix(ui): translate lifecycle and retake statuses`: AdminAttentionPage.tsx,
   AdminEmployeeDetailPage.tsx, ConfirmDialog.tsx and their relevant tests, plus
   this report and STATUS.md. Human-readable values; machine contracts unchanged.
5. `docs: record post-push QA verification`: this report and STATUS.md only, after
   the requested extra tests. No application changes or repeated behavior tests
   solely for this documentation checkpoint.

Before committing, the single timing-label hunk is grouped with its Final Exam
page in entry 3, keeping each tested file intact. Scope and behavior are unchanged.

This report and STATUS.md accompany the verified result. Preserve existing outputs,
Photos and the dirty main checkout. Stage only the mapped paths. No dependency/migration/content edits.
The only API addition is an authenticated GET for an employee's completed Final review;
grading, certification, attempts, deadlines and tenant boundaries remain unchanged.

## Commit and post-push verification — 2026-10-06

Four selective commits were created and pushed to the existing
`origin/codex/fix-sqlalchemy-asyncio` branch:

1. `9bc263a` — empty employee search.
2. `4a0ea58` — revoked-session handling.
3. `403767f` — completed Final Exam review and reload regression.
4. `142788f` — human-readable statuses and scope/evidence documentation.

Remote readback confirmed `142788f608e841bc42bfd561138144ce1142c8d7` before
post-push tests. No production source changed during this Git/test continuation.

| Fresh check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Pre-commit four focused frontend suites | 19 | 0 | 0 |
| Pre-commit PostgreSQL Final Exam service + API acceptance | 26 | 0 | 0 |
| Post-push full Playwright, all three viewports | 87 | 0 | 0 |
| Post-push PostgreSQL auth/session/lifecycle API suites | 40 | 0 | 0 |
| Read-only public staging HTTP smoke | 4 | 0 | 0 |

The 40 backend cases cover `test_auth_session.py`, `test_auth_csrf_logout.py`,
`test_auth_logout_others.py`, `test_auth_mfa_rbac.py`,
`test_auth_security_regressions.py` and `test_employee_lifecycle.py`. Executed with
pytest, `-q -p no:cacheprovider --tb=line`, existing Python 3.12 and the dedicated
test PostgreSQL environment. Browser execution used installed Playwright with
`--workers=1` and the same local strict-port wrapper, without a file filter.
All selected tests completed; this is not a new full-backend coverage gate.

Public smoke verified `/` and `/employee/final-exam` return 200, `/api/v1/health`
returns 200, and unauthenticated `/api/v1/auth/session` returns 401. Fresh Railway
readback after push shows API and web still SUCCESS on `main` at
`1bd384018ae304466c528edbf81e441b2b3a9dab`; the branch push did not deliver these
fixes. Hosted smoke proves old-version availability, not new-fix acceptance.

Final inventory contains only the 17 mapped source/test/documentation paths.
Committed diff whitespace checks passed. Existing outputs remain excluded; the
original dirty checkout and protected assets were not changed. This final
documentation-only checkpoint records these results under map entry 5; no test
rerun is needed solely for recording evidence.

## Pre-commit implementation evidence

### Result

- Empty employee searches now have their own message and a reset action. Failed
  requests do not claim that the team is empty.
- A protected request returning 401 ends the local session and explains the next
  step on the login page. Network failures and 403 do not log users out. A late
  failure from an old session cannot invalidate a new login.
- Employee history offers a read-only answer review after returning/reloading.
  Loading failures are retryable. Starting a new attempt clears the old review
  and invalidates any pending response; review controls are hidden while answering.
- Attention states, retake reasons/timing and employee lifecycle reasons display
  Ukrainian labels. Confirmation progress no longer always says activation.

### Contract and separate review

New `GET /api/v1/me/training/final-exam/attempts/{attempt_id}/result` reuses
`FinalExamFinishResponse`. The active-employee guard supplies organization,
location and employee scope; the existing ownership query additionally requires
a Final Exam assessment. Only completed attempts with a stored result expose
answers. No grading, result creation, deadline updates or audit events are added
by this reader. No migrations or dependencies.

A separate final code review checked authentication, all four ownership query
inputs, unfinished-answer protection, serializer reuse, session-race behavior and
failed-request UX. The PostgreSQL API scenario verifies unfinished 404, exact saved
review on repeated reads, unchanged result/audit counts, wrong scope/ID 404,
disabled membership 403 and unauthenticated 401. Browser mocks are not evidence of
deployment or live API integration.

### Executed checks

- RED: empty-search test failed on the old empty-team heading; session matrix had
  1 expected failure (401) and 2 passes (403/network); saved-review UI failed on
  the missing button; real PostgreSQL saved-review GET failed with 404; Attention
  test failed on untranslated labels. Filtered cases were not acceptance gates.
- Focused frontend suites: **19 passed, 0 failed, 0 skipped**.
- Full final Vitest: **166 passed, 0 failed, 0 skipped**, 32 files.
- Backend combined first GREEN attempt: **25 passed, 1 failed, 0 skipped**; the
  failure was the added disabled-membership fixture omitting its required timestamp.
  After correcting the fixture, the complete API acceptance scenario passed:
  **1 passed, 0 failed, 0 skipped**. The 25 Final Exam service cases passed in the
  combined run; backend production code did not change afterward.
- TypeScript, full frontend ESLint, changed-file Prettier, changed-file Ruff
  check/format, and full backend mypy (259 source files): passed.
- Local production build: passed; existing large-chunk advisory remains (542 kB JS).
- Browser acceptance: **18 passed, 0 failed, 0 skipped** on desktop (1440),
  compact (768) and mobile (375). Final Exam, retake/Attention, other-device logout
  and the vertical slice passed. Added reload/reopen checks expose all 20 stored
  answers while asserting the finish mutation happened exactly once. Viewports
  have no horizontal overflow.
- Final changed-file inventory and `git diff --check`: passed; index untouched.

The initial full Vitest run had **165 passed, 1 failed**: the wrapper forwarded an
extra undefined argument to a spy. Rest-argument forwarding preserves the original
call shape; the final full run above passed. Intermediate type/lint/format findings
were corrected before the final checks.

The first browser attempt reused an unrelated local site on the standard port:
5 observed failures before stopping the run. Those failures are environment
evidence, not Bacara acceptance. A temporary local config retained all three
projects, used a dedicated strict port and disabled server reuse. Its first load
failed on CommonJS/import.meta compatibility before tests; after correcting that
local helper, the complete selected browser run passed as reported above. Helper
and screenshots remain local under outputs and are excluded from the commit map.

Installed tools were used directly with the same configurations: Vitest with one
worker, `tsc -b --pretty false`, `eslint .`, Prettier for touched files and Vite build.
Initial pnpm testing and a cached Ruff check stopped before testing due to worktree
temporary-file permissions. Dependencies were not reinstalled; installed tools and
Ruff `--no-cache` completed. Python 3.12 used the existing environment, current backend
on the module path and secret-safe test settings. PostgreSQL was dedicated test-only.

### Changed-file inventory / selective staging plan

These explicit paths comprise the authorized selective publication inventory.
Local helpers and outputs are excluded.

- `frontend/src/admin/AdminEmployeesPage.tsx`
- `frontend/src/admin/AdminFlow.test.tsx`
- `frontend/src/session/SessionContext.tsx`
- `frontend/src/session/SessionGate.test.tsx`
- `frontend/src/auth/LoginPage.tsx`
- `backend/app/services/final_exam_results.py`
- `backend/app/api/routes/assessments.py`
- `backend/tests/api/test_operations_hardening_acceptance.py`
- `frontend/src/employee/EmployeeFinalExamPage.tsx`
- `frontend/src/employee/EmployeeFinalExamPage.test.tsx`
- `frontend/e2e/final-exam-slice.spec.ts`
- `frontend/src/admin/AdminAttentionPage.tsx`
- `frontend/src/admin/AdminAttentionPage.test.tsx`
- `frontend/src/admin/AdminEmployeeDetailPage.tsx`
- `frontend/src/ui/ConfirmDialog.tsx`
- `docs/testing/manual-qa-fixes-2026-10-06.md`
- `STATUS.md`

### Delivery boundary

Candidate on `codex/fix-sqlalchemy-asyncio`, based on `362183a`, is committed and
pushed. Additional post-push checks are recorded above. PR, merge, deployment and
hosted data changes remain separate; no such action was performed. Next delivery
gate: separately authorize integration into main and deployment, then repeat
authenticated staging checks for both roles on the exact delivered revision.
