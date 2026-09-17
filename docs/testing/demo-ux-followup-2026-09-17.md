# Demo UX follow-up — CRA-271

## Authorized Git follow-up — 2026-09-17

After reviewing the local outcome, Denys explicitly requested commit + push. The six
checkpoint boundaries below are now authorized for selective local commits and normal push
to the existing origin/main. Fresh fetch found origin/main 32 commits behind local main,
with no divergence; normal push includes that existing ancestry. Earlier unrelated dirty
changes, Photos and local output remain excluded. PR, deploy, hosted migration, question-bank
publication and email sends are not included.

Focused checks rerun before the implementation commits: Home 6 passed; question backend
units 21 passed and assessment frontend 20 passed; Lesson/Menu 18 passed; Results 10 passed;
history frontend 6 passed and backend history 3 passed. Each staged diff was reviewed and
passed `git diff --cached --check`. All previous implementation-checkpoint statements below
about absence of commits describe the state before this follow-up authorization.

## Scope and acceptance

Denys approved tests followed by local fixes for the September 17 screenshots. He reported
successful mobile use, password reset and completion of the Employee journey; the supplied
Final Exam screenshot shows 19/20 (95%). This is owner-reported hosted evidence, not a new
automated staging run by this agent.

Active contract: [CRA-271](https://linear.app/craftspacee/issue/CRA-271), START HERE and FINAL
CRA-12 with the additive business-history and public question-selection decisions. Repository
and backend AGENTS, local harness, global Denys harness and RTK instructions were read.
The `bug-reproducer` and `ui-ux-pro-max` workflows were used. Current direct authorization
explicitly covers both RED tests and subsequent production-code edits.

Repository: existing main worktree at bf4790c. Initial worktree had 36 status entries and an
empty index; unrelated changes and Photos were preserved. No Git commit, push, dependency,
remote deployment, provider call, email send or hosted data mutation was performed.

## Implemented behavior

- Home gives earned certification precedence over the old `open_final_exam` next action.
  The saved certification/date and result link are visible; an active retake remains separate.
  Incomplete new training retains its learning action.
- New description-recognition candidates contain one-answer semantics and at most four
  verified alternatives from the lesson. Selection is deterministic and independent of input
  order. Interactive Training, Practice and Final Exam use radio controls for this public
  marker, retaining the existing recognition answer wire format. Copy editing preserves the
  marker; backend review rejects a change to provenance-bound selection semantics.
- Linked Menu cards carry a safe internal return destination to the originating lesson/block.
  Both Menu and the detail dialog expose the return link; the lesson restores focus/scroll.
  External destinations, other app areas and traversal-like paths are rejected.
- Final Exam shows score, correct/incorrect counts, critical-error count and completion date.
  Review defaults to mistakes, with a button to show all answers. Returning later shows the
  persisted latest-result summary. Admin Results now includes translated training status,
  exam score/date and a detail view with Practice score, exam history and completed-answer
  review using the existing authorized endpoint.
- Admin navigation now opens **Історія змін**. The page shows item, timestamp, author email
  and only changed business fields with **Було / Стало**, on desktop and mobile. The separate
  Operator technical audit remains unchanged.

## Business-history contract and persistence

`GET /api/v1/organizations/{organization_id}/menu-change-history` requires same-organization
Admin access and verified MFA. `limit` is 1–100 (default 50); `cursor` is opaque and bounded.
The result has `items` and `next_cursor`, ordered by creation time and event UUID descending.

Migration `0020_menu_change_history` adds `menu_change_events`. Item creation, update and
removal through the existing Draft item service record a before/after snapshot atomically
with the successful write. No-op business changes and rejected stale writes produce no row.
Actor email is captured at write time rather than joined from the user's current address.
Fields are explicitly allowlisted: name, description, price/currency, availability, component
status/names/optionality, allergen status/codes. Source references, credentials, assessment
answers and arbitrary audit payloads are excluded. Technical audit storage is unchanged.

The page describes Draft edits; it does not claim they are already published. Recording
covers manual item CRUD, not historical imports, bulk publication or hierarchy-only changes.
No speculative history backfill is performed. Email digests are not implemented: recipients,
cadence and delivery policy need a separate bounded decision.

The question prompt addition is `selection_mode: "single"` (optional). Existing immutable
Published questions and completed attempts are not rewritten. Therefore the currently hosted
80-question bank will retain its existing option counts until a separately reviewed new-bank
publication. The frontend does not inspect hidden correct-answer keys to infer cardinality.

## RED → GREEN evidence

| Boundary | Intended RED | GREEN |
| --- | --- | --- |
| Certified Home, including retake | 2 failed, 4 passed | 6 passed |
| Bounded description generation | 1 failed, 11 passed | 12 passed |
| Exclusive recognition control | 1 failed, 6 passed | combined Interactive/Practice/Final: 15 passed |
| Lesson/Menu return | 2 failed, 12 passed | 14 passed |
| Results summary and review | 3 failed, 6 passed; Admin detail 1 failed | 10 passed |
| Business history API/MFA | 2 failed (missing route) | final history suite: 3 passed |
| Business history UI/navigation | 2 failed, 4 passed | 6 passed |
| Selection-semantic review guard | 1 failed, 8 passed | question unit suites: 21 passed |
| Preserve selection mode in editor | 1 failed, 3 passed | 4 passed |

All counts above are per run and overlap; do not sum them into a unique total.

### Final checks

Commands run from the relevant backend/frontend directory, using the existing RTK wrapper.
PostgreSQL commands loaded the ignored test environment according to `.harness/TESTING.md`,
verified `APP_ENV=test`, the dedicated `horeca_test` database name, and matching test/runtime
URLs before schema recovery. No environment values were printed deliberately or copied here.

- Backend focused combined run: `rtk ..\.venv\Scripts\python.exe -m pytest
  tests/unit/test_question_generation.py tests/unit/test_question_review.py
  tests/integration/test_question_generation_service.py
  tests/integration/test_menu_change_history.py tests/integration/test_menu_item_service.py
  tests/api/test_menu_admin_api.py tests/migration/test_migrations.py
  --tb=short -q -p no:cacheprovider`: **61 passed, 0 failed, 0 skipped**.
- `rtk ..\.venv\Scripts\python.exe -m ruff check .`: passed.
- `rtk ..\.venv\Scripts\python.exe -m ruff format --check .`: 267 files formatted.
- `rtk ..\.venv\Scripts\python.exe -m mypy app tests`: 244 files, no issues.
- Dedicated test schema recreated through Alembic base → head; `alembic check` reports no
  missing upgrade operations. The final combined run includes all existing migration tests.
- `rtk pnpm test --maxWorkers=2`: **124 passed, 0 failed, 0 skipped**, all 28 test files.
  Four return-destination checks were added afterward; final focused run of Menu, Question
  Bank, Operations and Final Exam: **20 passed, 0 failed, 0 skipped**.
- `rtk pnpm test:e2e final-exam-slice.spec.ts operations-hardening-slice.spec.ts --grep
  "Employee completes Final|menu change history" --workers=1`: **6 passed, 0 failed,
  0 skipped** at 1440, 768 and 375px. Synthetic API responses; no hosted acceptance claim.
  Mobile exam/history and desktop history screenshots were inspected. No horizontal overflow.
- `rtk pnpm lint`: passed. `rtk pnpm build`: passed (includes TypeScript).
- Repository-wide `rtk pnpm format:check` found an existing formatting difference in
  `src/admin/AdminTrainingPage.test.tsx`; that unrelated pre-existing file was preserved.
  All paths changed by CRA-271 were formatted with the installed Prettier executable.

Initial broad checks are retained as evidence: unrestricted frontend workers timed out two
308-item DOM tests (122 passed, 2 failed). The entire suite passed with two workers without
changing assertions or timeouts. The first backend combined run was 57 passed / 3 failed:
the table inventory needed the new table, and a historical migration roundtrip left the test
schema inconsistent. Dedicated synthetic test data/schema recovery was followed by a passing
isolated backfill test and the passing full combined 61-test rerun. The root cause of that
initial transient roundtrip inconsistency was not established. Initial lint/type errors in
new presentation/test code were corrected; final lint/build pass. No full backend coverage
run or full Playwright suite was claimed.

## Reviewable file boundaries / future selective staging

No staging or commits were performed. Preserve these coherent checkpoints if commits are
authorized later; split shared-file hunks and exclude every pre-existing unrelated change.

1. Home: `frontend/src/employee/ActiveHomePage.tsx` and `.test.tsx`.
2. Questions: `backend/app/schemas/assessment.py`, `services/question_generation.py`,
   `services/question_review.py` (selection hunks only), corresponding two unit test files;
   `frontend/src/employee/answerSelection.ts`, Interactive Training component/test, Practice
   and Final Exam selection hunks, Admin Question Bank component/test, candidate API type.
3. Navigation: EmployeeLearningLessonPage, EmployeeLearningPages.test, EmployeeMenuPage and
   EmployeeMenuPage.test under `frontend/src/employee`.
4. Results: `frontend/src/ui/ExamResultReview.tsx`, Final Exam component/test/review hunks,
   AdminResultsPage, AdminResultDetailPage and its new test, AdminFlow.test, exam CSS and
   `frontend/e2e/final-exam-slice.spec.ts`.
5. History: `backend/app/models/menu_history.py`, model export, schema/service of the same
   name, CRUD hooks in `services/menus.py`, history route hunks in `api/routes/menus.py`,
   migration 0020, integration/test_menu_change_history.py, conftest cleanup inventory and
   migration/test_migrations.py table inventory; frontend AdminAuditPage, history API types,
   AdminShell and test, OperationsPages.test, history CSS and operations-hardening E2E hunks.
6. Evidence: this report and the new top checkpoint in `STATUS.md`.

Shared files already had accepted changes before CRA-271: route menus.py, question_review.py,
frontend contracts.ts/styles.css and STATUS.md. Never stage those entire files without review.
Photos, outputs, test screenshots, caches and local environment files are excluded.

## Delivery boundary

Local implementation and focused verification are complete. Selective commit + push is
authorized by the follow-up above; application delivery remains separate.
Deploy API migration 0020 together with the business-history API before enabling
its frontend page. A reviewed new question-bank publication is a separate data action.
The running hosted application has not received these local UX changes.
