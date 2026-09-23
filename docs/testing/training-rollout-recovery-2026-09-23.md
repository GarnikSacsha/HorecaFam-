# Training rollout panel recovery — 2026-09-23

Denys requested fixing the lost Admin rollout panel after the approved lesson-content
correction. This is the bounded recovery follow-up to CRA-275, not a new content rewrite.

## Problem and change

Replacement publication persisted the rollout, but AdminTrainingPage retained its ID only
in React state. Visiting Question Bank or reloading lost the only visible entry point.

The protected Training version collection now adds nullable `rollout_id`: the latest
non-cancelled rollout for the exact current Published version and its base version, scoped
by organization, location and stable Training. No Published/base version means null.
Completed rollouts remain visible as completed. No new route, dependency or migration.

The editor restores that server ID on workspace load, clears it while changing location,
and remounts the panel for a changed scope. Opening the workspace remains read-only.
Preview, preserve/repeat decisions, confirmation, revision checks and certification semantics
are unchanged. The optional frontend field supports an API-first rolling deployment.

## Atomic commit map

One boundary, proposed message: `fix(training): restore persisted rollout panel on reload`.

- `backend/app/schemas/training.py`
- `backend/app/services/training_queries.py`
- `backend/tests/api/test_training_rollout_api.py`
- `frontend/src/api/contracts.ts`
- `frontend/src/admin/AdminTrainingPage.tsx`
- `frontend/src/admin/AdminTrainingPage.test.tsx`
- this report and `STATUS.md`

Focused gate: PostgreSQL rollout/Admin API tests, Training editor/audience component tests,
changed-file lint/format, type checks, production frontend build and diff review.
No Git index changes, commit, push or hosted deployment performed for this patch.

## Verification

- Intended RED: four API cases failed with missing `rollout_id`; frontend reopening case
  failed because the confirmation panel was absent (12 other cases filtered out).
- Initial fixture errors: preview/completed rollout timestamps, then archived Training
  timestamp violated lifecycle constraints. Fixtures were corrected without relaxing checks.
- GREEN: PostgreSQL rollout/Admin API 18 passed, 0 failed, 0 skipped.
- GREEN: editor/audience Vitest 19 passed, 0 failed, 0 skipped; reopening and location switch
  assert that no publication/confirmation request occurs.
- TypeScript, production build, changed-file ESLint and mypy passed.
- Initial Ruff import order and test formatting findings corrected.
- Environment: pnpm wrapper attempted dependency reconciliation and aborted; existing local
  Vitest/TypeScript/Vite entry points were used directly without installing dependencies.
  Sandbox EPERM required escalated frontend checks. One PowerShell exit-code guard was
  malformed; TypeScript was rerun independently and passed, and Vite build passed.
- Final review: query includes tenant/location/Training/source/target scope, performs only a
  SELECT, ignores cancelled and noncurrent transfers, and leaves mutation authorization intact.
  No credentials, hosted records, generated artifacts or unrelated files are in this patch.
- Full backend coverage and live delivery acceptance were not rerun.

## Hosted continuation

Before this code patch, the authorized content workflow published Training v3 with 11 ice
cream cards and 11 associated variant blocks removed from Food; Desserts stayed unchanged.
The existing 60 authored questions were copied and approved, and Final was published ready.
All four lessons, Practice and Final reported ready. Employee rollout confirmation remains
pending; no new employee test attempt or completion was created.

After separately authorized API/web delivery, reopen Admin Content, refresh the rollout
preview, verify preserve-completion impact, and finish the already-authorized v2-to-v3 transfer.
Then verify Food/Desserts, existing progress and certification in the employee/admin UI.
