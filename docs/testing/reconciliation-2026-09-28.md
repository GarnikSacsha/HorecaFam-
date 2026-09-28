# CRA-275 — audit follow-up, 2026-09-28

## Approved local source checkpoints — 2026-09-28

Denys approved the prepared four-entry local commit map with “Погнали дальше”.
Completed source checkpoints: Employee a162b6a, Admin 6658901, frontend LF policy
02a2329. This documentation checkpoint completes the map; no push, deployment or
hosted data operation is included. The source is now recoverable in local Git.
Earlier “uncommitted” paragraphs below describe the preparation state.

The exact source was already verified: 160 unit and 87 browser tests passed with zero
failures/skips; types/lint/format/build passed. Source has not changed since those gates,
so application tests were not repeated solely for committing. Each commit's exact
staged inventory and whitespace checks passed. Next: separately approve publication
of this four-commit branch; content-v5 and rollout gates remain independent.

## Scope and authority

Denys requested executing the repository audit plan in order. This continuation closes
local frontend quality gates, reconciles current documentation, and prepares selective
source checkpoints for the already delivered Employee/Admin fixes. CRA-275 remains
In Progress. No new product feature, API/schema, dependency or hosted data change.

Current source: registered worktree 5c12, branch codex/cra-275-lesson-category-ux,
HEAD 60bf1599324040e62c5cea12725df17d111cdb50. The old dirty main checkout is preserved.
The September 25 delivered artifact includes eight uncommitted frontend overlays.

## Ordered selective commit map

Local commits for all four entries were explicitly authorized after review. Push,
delivery/publication/employee rollout remain separately gated.

1. `fix(frontend): simplify employee menu details`
   - frontend/src/employee/EmployeeMenuPage.tsx
   - frontend/src/employee/EmployeeMenuPage.test.tsx
   - frontend/src/employee/EmployeeLessonMenu.test.tsx
   - frontend/e2e/lesson-menu-overlay.spec.ts
   - frontend/e2e/vertical-slice.spec.ts
   - Existing delivered renderer and regression tests; align the publication scenario
     with the accepted September 25 dialog contract. Preserve publication assertions,
     guest description, price, allergens, close and focus. Verify focused publication
     browser cases, then full Playwright and frontend unit/static/build gates.
2. `fix(frontend): identify bound menu cards in lessons`
   - frontend/src/admin/AdminTrainingPage.tsx
   - frontend/src/admin/AdminTrainingPage.test.tsx
   - frontend/src/admin/useTrainingMenuItems.ts
   - frontend/src/admin/useTrainingMenuItems.test.tsx
   - Preserve delivered scoped pagination, retry and stale-response isolation.
     Review exact diff and verify full frontend unit/static/build gates.
3. `chore(frontend): preserve LF line endings across checkouts`
   - frontend/.gitattributes
   - LF-only working-copy normalization of tracked frontend files covered by Prettier.
   - Narrow frontend policy only; no global Git setting, index normalization or binary
     change. Verify full Prettier, Git attributes and unchanged text after CRLF removal.
     Existing Git blobs are expected to be LF, so normalization should add no source diff.
4. `docs: reconcile CRA-275 audit and remaining acceptance`
   - STATUS.md
   - CONTEXT.md
   - docs/testing/README.md
   - docs/testing/menu-detail-polish-2026-09-25.md
   - docs/testing/lesson-category-ux-cra-275.md
   - docs/testing/training-rollout-recovery-2026-09-23.md
   - docs/testing/reconciliation-2026-09-24.md
   - docs/deployment/menu-polish-cra-275-2026-09-25.md
   - docs/testing/reconciliation-2026-09-28.md
   - Preserve historical evidence and existing reports; remove contradictions in current
     summaries, distinguish audit checks from fresh follow-up checks, validate file links
     and exact diff. Depends on completed verification above.

Formatting/documentation use the harness TDD exception: no runtime behavior changes.
The test correction follows the accepted contract, not a new production implementation.
No Photos, outputs, local helpers, environment files, caches or runtime artifacts are
part of these staging lists.

## Audit evidence (preceding read-only pass)

Full backend: 994 passed, 0 failed, 0 skipped in 2807.64 seconds.
Independent same-run coverage: statements 94.38%, branches 81.38%, critical aggregate
89.71%; all gates passed. Ruff and strict mypy passed. No backend changes are planned.

Frontend: 160 unit tests passed; types/lint/build passed; Playwright 84 passed and
3 failed (the same removed composition expectation across three viewports).
Prettier: 101 failures, all proved CRLF-only by checking normalized text in memory.
135 delivery archive files matched the manifest; public JS/CSS matched the fresh build.
These are earlier audit results, not reruns of this implementation continuation.

## Follow-up execution

The sandboxed focused Playwright launch failed before tests with spawn/mkdir EPERM.
The permitted rerun reached the actual scenario: 0 passed / 3 failed / 0 skipped,
all at the removed composition expectation. After correction: 3 passed / 0 failed /
0 skipped. This is test-contract maintenance; no new production behavior was added.

Full Playwright: 87 passed / 0 failed / 0 skipped. Full Prettier, TypeScript, ESLint
and Vite build passed. The first sandboxed ESLint eventually passed too; the parallel
permitted rerun also passed. No source changed between those equivalent lint runs.
Full frontend unit run: 160 passed / 0 failed / 0 skipped across 32 files in 143.63 seconds.

Normalized CRLF to LF in 101 tracked frontend working files after checking normalized
content with Prettier. The already edited publication test was written as LF separately.
Git diff contains no new mass source changes from normalization. frontend/.gitattributes
enforces LF for frontend source/config/document extensions only; binary assets, backend,
Git index and global settings are unchanged. Git attribute checks verified this boundary.
Vite retains index-CyBrlEEU.js and index-Ba8zXRak.css; the existing chunk-size warning remains.

The publication scenario still checks review, explicit confirmation, draft publication
and Employee readback; it now asserts the accepted absent composition, retained price,
one allergen label, close and restored focus. No assertions were skipped or timeouts raised.

Self-review covered the existing delivered Employee renderer and Admin loader/diffs:
source labels remain display-only; unknown source facts are not promoted; Admin reads
remain bound to the version with pagination/revision/cursor checks and stale-result
isolation. No write payload, endpoint, authorization or schema changed.

## Remaining hosted sequence

Latest accepted September 25 evidence: published/assigned v4 preserved; draft v5 cleaned
to 81 cards (31/20/13/17), lesson blocks 45/37/25/33. No fresh hosted content read in this
local follow-up. Do not repeat duplicate deletion.

After explicit authorization: re-read draft revision and bindings, publish v5, recover
the unchanged 60 authored questions if needed (Final quotas 10/4/3/3, threshold 70%),
verify lesson/Practice/Final readiness, preview the two-employee rollout and preserve
completion/results/certification before execution and authenticated acceptance.
Practice cross-version presentation and the 308-item proposal remain separate decisions.

CRA-122 worker/cron, provider, backup/restore and venue acceptance require their own
current-state preparation and execution approvals. Do not infer Done from deployment.

## Commands for the fresh follow-up

Run from frontend using installed entrypoints; each command is prefixed with rtk proxy.
No dependency synchronization or installation was needed.

```text
node node_modules/@playwright/test/cli.js test e2e/vertical-slice.spec.ts --grep 'admin JSON review confirm and atomic menu publication' --workers=1
node node_modules/@playwright/test/cli.js test
node node_modules/vitest/vitest.mjs run --maxWorkers=1 --reporter=dot
node node_modules/prettier/bin/prettier.cjs --check .
node node_modules/typescript/bin/tsc -b --pretty false
node node_modules/eslint/bin/eslint.js .
node node_modules/vite/bin/vite.js build
```

## Final reconciliation and review

Linear CRA-275 and START HERE were updated and re-read: September 28 evidence present,
CRA-275 remains In Progress, no automatic acceptance or unrelated issue closure.
Current delivery/duplicate checklist entries now reflect September 25 completion.

Documentation file-target validation: 68 Markdown files, 386 relative links, zero
missing targets (anchors not validated). Initial sandbox helper could not spawn Git;
the permitted read-only rerun passed. Git diff --check passed; index remains unstaged.
Final text diff has only the 12 expected tracked paths; the seven untracked mapped
source/config/report paths are explicit in the map above. Existing outputs are excluded.
Windows Git status can still mark normalized LF files because cached checkout metadata
reflects CRLF; their normalized Git content has no diff. No index refresh/staging was
used to hide these working-copy marks. The old main checkout inventory is unchanged.

Fresh separated review of the publication assertions, delivered renderer/loader tests,
LF scope and documentation found no new blocking issue within this local boundary.
Hosted v5 publication/rollout, private Railway inventory and venue acceptance remain
unverified here. No claim of full pilot acceptance or new security audit.

Next decision: authorize the four selective local commits in this report. Push,
deployment and hosted publication/rollout remain independent subsequent approvals.
