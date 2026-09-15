# CRA-202 — Training audience editor

## Scope and authorization

Denys continued the September 15 audit plan with the Training audience editor named as the next step. This is local implementation on main after d28bced. Local commits, remote publication, deployment, provider calls and non-test data writes are separate and were not performed.

Canonical navigation: Linear START HERE; FINAL CRA-12 accepted Slice 4 audience/applicability closure; [CRA-202](https://linear.app/craftspacee/issue/CRA-202/add-safe-training-audience-read-and-admin-editor) defines the additive read and bounded implementation map. Existing PUT rules remain unchanged.

## Contract delta

Added GET `/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions/{version_id}/audiences`.

Response uses the existing `TrainingAudienceResponse`:

- training_version_id;
- revision;
- operational_role_ids, complete and sorted.

The route requires the existing Organization Admin and completed-MFA guard. Organization/location/version scope uses non-enumerating 404. Draft, Published and Archived versions are readable by an authorized Admin. No audience is represented by an empty list. Archived role references remain in the response.

Revision and role IDs come from one SELECT with an outer join, so the read cannot combine a previous revision with a subsequent replacement set. It does not change audience, version revision, assignments or audit events. Existing authentication session activity remains governed by the shared authentication layer.

No migration, dependency, existing PUT payload, publication or assignment behavior changed. New GET is an additive API requirement: deploy backend support before using this frontend. A frontend against an old backend shows a read error and blocks audience saving.

## Admin experience

The editor appears for a Training Draft and loads both the full organization role catalogue and the exact version audience before allowing a replacement.

- Explicit checkbox selection and Save; no mutation from reading.
- At least one active role is required.
- Selected archived or unavailable roles remain visible until explicitly removed.
- PUT carries the audience snapshot revision and CSRF token.
- Duplicate pending saves are blocked.
- A failed save preserves choices. Revision/immutable conflicts block another save until explicit reload; reload warns that it replaces local choices.
- Scope changes discard late reads. The page keys the panel by organization/location/version.
- Saving updates the parent revision and readiness without resetting local module/lesson text. Location changes and other save buttons are disabled during the mutation.
- The existing draft-only backend remains authoritative. Concurrent edits may require reloading the audience before saving; they are never silently overwritten.

## Files and prospective commit boundaries

Implementation was initially left unstaged. Denys subsequently authorized the three local commit boundaries below and staging API/web deployment on September 15. Deployment must preserve the existing CRA-172 overlay; Git push and non-test content mutations are not included.

1. Backend read and tests:
   - backend/app/services/training_audiences.py
   - backend/app/api/routes/training.py
   - backend/tests/api/test_training_audience_api.py
   - Intended commit: feat(training): expose scoped version audience read
2. UI and integration:
   - frontend/src/admin/AdminTrainingAudiencePanel.tsx
   - frontend/src/admin/AdminTrainingAudiencePanel.test.tsx
   - frontend/src/admin/AdminTrainingPage.tsx
   - frontend/src/admin/AdminTrainingPage.test.tsx
   - frontend/src/api/contracts.ts
   - frontend/e2e/training-slice.spec.ts
   - Intended commit: feat(admin): edit training audience explicitly
3. This evidence document:
   - docs/testing/training-audience-editor.md
   - Intended commit: docs(training): record audience editor verification

## Verification — 2026-09-15

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Focused audience API | 6 | 0 | 0 |
| Audience + publication + Admin Training API (includes the six above) | 24 | 0 | 0 |
| Full frontend, 25 files | 103 | 0 | 0 |
| Final panel + existing Training editor recheck (included in frontend total) | 12 | 0 | 0 |
| Final browser audience/save/publication/Employee read, three viewports | 3 | 0 | 0 |

The full frontend run preceded the final reuse of existing layout classes and strengthening of the late-response test; those final files passed the focused 12-test and three-viewport browser rechecks. No new test count was added by replacing that test.

Ruff check/format and strict mypy passed for the three backend files. ESLint/Prettier passed for six frontend files. Typecheck and production build passed. Final diff whitespace and selective inventory checks passed.

RED evidence:

- Backend: 1 failed, 1 passed; the new read assertion received HTTP 405 before the GET route existed.
- Frontend: 4 failed, 1 passed before panel implementation, for missing audience selection/error/retry controls. The initially vacuous unmount check was replaced with an actual delayed old-version response after scope change.
- Two subsequent backend fixture failures came from missing published_by_user_id in synthetic Published/Archived records. Corrected the fixture to satisfy the existing lifecycle constraint, then all six passed.
- An initial shared frontend mock did not implement the new read, producing a second alert in the existing conflict test. Updated the mock to the explicit response contract.
- One concurrent full-suite attempt had 102 passed and one timeout in the unchanged 308-item Admin Menu test (5-second budget), while API/browser suites were also running. The same frontend command alone passed all 103; timeout and prior Menu tests were not changed.

Commands (from backend after the harness's secret-safe test-environment validation):

```text
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_training_audience_api.py tests/api/test_training_publication_api.py tests/api/test_training_admin_api.py -q -p no:cacheprovider --tb=line --show-capture=no
rtk ..\.venv\Scripts\python.exe -m ruff check app/services/training_audiences.py app/api/routes/training.py tests/api/test_training_audience_api.py
rtk ..\.venv\Scripts\python.exe -m ruff format --check app/services/training_audiences.py app/api/routes/training.py tests/api/test_training_audience_api.py
rtk ..\.venv\Scripts\python.exe -m mypy app/services/training_audiences.py app/api/routes/training.py tests/api/test_training_audience_api.py
```

Frontend:

```text
rtk pnpm test --maxWorkers=2
rtk pnpm test --maxWorkers=2 src/admin/AdminTrainingAudiencePanel.test.tsx src/admin/AdminTrainingPage.test.tsx
rtk pnpm test:e2e --grep "admin publishes Training"
rtk pnpm typecheck
rtk pnpm build
```

ESLint and Prettier used their existing node_modules CLI entry points against the six listed frontend files. Browser tests use synthetic mock API responses; PostgreSQL tests use the existing dedicated local test database. Desktop/mobile final screenshots were visually inspected; compact browser scenario also passed. Screenshots remain ignored test output.

## Separate boundary review

Reviewed after implementation: existing Admin/MFA dependency, exact scope predicates and foreign-key scope invariants, one-statement read consistency, absence of domain writes, full role catalogue, complete replacement semantics, CSRF, stale revision rejection, and unknown/archived roles. Existing service-level PUT validation remains unchanged. Tests exercise anonymous denial, missing MFA, ordinary member denial, unknown/wrong scope, retained versions, exact readback, revision and audit preservation.

No critical/high issue was identified in this bounded review. This is not a full repository security scan or refreshed full backend coverage gate.

## Remaining boundaries

- The initial detailed verification update to Linear was rejected by automatic approval review. Denys subsequently explicitly authorized that transfer; the report was saved to CRA-202 and read back successfully on September 15. The issue remains In Progress pending implementation acceptance.
- Local commits and staging API/web deployment were subsequently authorized; execution evidence is recorded separately from the original implementation checks.
- CRA-172 changes in worktree 54bf overlap Training integration files. Preserve and reconcile that overlay before selecting any release candidate; this change did not touch that worktree.
- No live audience, role, assignment or publication was changed.
- Full backend integration/coverage, full Playwright suite and hosted acceptance were not run for this bounded read/UI change.
- Unrelated dirty documentation, Photos and outputs remain unchanged.
