# CRA-275 — Menu detail polish, 2026-09-25

## Latest delivered result — 2026-09-25

Both fixes are now delivered with explicit approval. Exact web deployment, HTTP10/0/0
and live Employee/Admin evidence: [delivery report](../deployment/menu-polish-cra-275-2026-09-25.md).
Eight duplicate pairs matched exact item/version bindings; redundant occurrences were
removed only from v5. Reload confirms 81 cards and preserved companion blocks. Published
v4 and employee progress remain intact. This supersedes local-only and pending-removal
wording below. Remaining: separate publication/assessment-recovery/rollout approval,
live acceptance after that step, Git checkpoint and separate Practice-history decision.

All pairs use Menu version cbd7060d-6f52-4cb5-89de-017940f69c5c. Verified item bindings:

| Source key | Exact item ID | Removed v5 block position before edits |
| --- | --- | ---: |
| dish-1720026 | d2fc9ec2-1f02-4cb5-bee7-06ac8d68ebb6 | Drinks23 |
| dish-1887140 | 49481f06-8cf9-46c2-9766-bbb6f0a3edf6 | Drinks24 |
| dish-1720027 | a26a8fcc-2a66-4c4d-ad7b-7ade8ff61203 | Drinks25 |
| dish-968565 | b54cae7c-cc2a-4cf0-9e9f-faaa6322e679 | Drinks26 |
| dish-1720029 | 24df6c0a-ceab-4a16-b90a-d9bbd017f1da | Drinks27 |
| dish-560651 | 9c60ca16-5be2-43e6-8015-c8763319c36e | Drinks31 |
| dish-1521118 | 456e6052-e49a-47f8-8bf0-1f6db74d77f2 | Other9 |
| dish-1521119 | 153e4499-7212-4e34-8588-2d3f63af427a | Other10 |

Deletion proceeded in descending original block order with a saved-count readback
after each change. Full remaining text/order comparisons passed for both affected
lessons. Fresh reload counts: Food31/45, Dessert20/37, Other13/25, Drinks17/33
cards/blocks; zero unresolved names, zero alerts, publication button enabled. No Menu
item/question deletion, new attempt, v5 publication or employee transfer occurred.

## Current result and ordered task checklist

Employee polish and Admin card identity were delivered September 25. Hosted v4 remains
active; draft v5 now has 81 cards after eight exact-binding duplicate removals. The
latest delivered checkpoint supersedes the preparation/access blockers retained below.
Acceptance remains open; publication and rollout require separate authorization.

- [x] Remove Employee composition/administration clutter and retain existing labels.
- [x] Show existing Admin card names from the bound Menu version; expandable binding
  details expose exact item/version IDs and source keys for duplicate verification.
- [x] Verify local code and reconcile STATUS, CONTEXT, testing index and historical
  report pointers, plus the current Linear checklist.
- [x] Separately approved frontend delivery completed; the
  [135-file candidate](../deployment/menu-polish-cra-275-2026-09-25.md) reached SUCCESS.
- [x] Verified eight actual bindings and removed only redundant draft-v5 blocks.
  Variants, Menu items and question links preserved; reload confirmed card counts
  Food31, Dessert20, Other13, Drinks17 (81 total).
- [ ] Authorize the reviewed selective Git checkpoint; delivered overlays remain uncommitted.
- [ ] Separately approve publication, recover/check assessment bindings and readiness,
  then review/execute the employee rollout with completions preserved.
- [ ] Complete hosted Employee/Admin checks and owner acceptance before closing CRA-275.
- [ ] Decide desired cross-version Practice presentation separately. Current filtering
  follows the version-specific contract; no claim that old data was deleted.

### Admin implementation and final verification

Changed AdminTrainingPage.tsx and its regression test; added useTrainingMenuItems.ts
and its six tests. One version-scoped paginated read sequence supplies all existing
card names instead of one request per card. No read occurs without a bound menu or
existing cards. Opaque cursors are encoded; revision changes/repeated cursors reject
partial labels. Scope changes immediately hide stale labels, late responses are
ignored, and failed reads provide retry. Missing items have an explicit fallback.
Existing block IDs, mutation handlers, order, payloads and API contracts are unchanged.

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Admin regression RED (name absent) | 0 | 1 | 13 filtered |
| Editor + picker + loader GREEN | 24 | 0 | 0 |
| Full frontend, 32 files | 160 | 0 | 0 |
| Final loader test rerun after lint correction | 6 | 0 | 0 |

The counts overlap. TypeScript, final full ESLint, scoped Prettier and Vite build passed. Lint initially
reported an async test callback without await; the first correction triggered the
await-thenable rule. The final explicit microtask flush passed the focused lint check
and all six loader tests. Production bundle index-CyBrlEEU.js built successfully;
the existing over-500-kB chunk warning remains. Earlier six Employee browser checks
were not rerun for the Admin-only change. No new backend, browser visual or hosted
acceptance gate is claimed for the new Admin renderer.

Commands used installed Node entrypoints: vitest run (focused files/full suite,
--maxWorkers=1 --reporter=dot), tsc -b --pretty false, eslint (scoped/full), prettier
--check on the four Admin files, and vite build. No dependency installation.
Final verification: 146 local Markdown links checked, zero broken; git diff --check
passed (existing line-ending notices only). Exact source diff and file inventory were
reviewed; no secrets, runtime artifacts, backend or unrelated source were added to
the change. Linear readback confirms the September 25 checklist and 160-test evidence
in CRA-275 and START HERE; CRA-275 remains In Progress. The task's existing dirty
documentation is preserved, not overwritten or staged.

## Approved Admin extension and commit map

Denys explicitly approved the Admin identity prerequisite and documentation/task
synchronization. CRA-275 records this scope. Ordered selective boundaries (no commit
authorization):

1. Existing Employee renderer correction and its three test files, this report:
   `fix(frontend): simplify employee menu details`; recorded 153 unit / 6 browser
   passes plus quality checks. Preserve this independently reviewable boundary.
2. AdminTrainingPage.tsx, AdminTrainingPage.test.tsx, useTrainingMenuItems.ts and
   useTrainingMenuItems.test.tsx: `fix(frontend): identify bound menu cards in lessons`.
   Reuse version-scoped paginated reads; verify name/binding, failures, pagination,
   stale scope isolation with RED/GREEN, adjacent editor/picker tests and quality gates.
3. STATUS.md, CONTEXT.md, docs/testing/README.md, this dated report and current
   pointers in lesson-category-ux-cra-275.md, training-rollout-recovery-2026-09-23.md,
   reconciliation-2026-09-24.md: `docs: reconcile menu polish and remaining acceptance`.
   Documentation-only TDD exception; verify links, diff and Linear readback. Preserve
   historical evidence; do not rewrite product contracts or mark acceptance complete.

Hosted duplicate cleanup depends on delivering the verified editor. Publication,
assessment recovery and employee rollout remain a later separately approved boundary.

## Scope and ordered boundaries

Denys explicitly requested removing the composition section and source/verification
administration copy from Employee item details, retaining useful descriptions and
existing allergen labels. He then authorized proceeding through the audit plan.
This direct presentation decision supersedes the earlier visible-warning wording
for this screen; source provenance and verification status in the API remain unchanged.

1. `fix(frontend): simplify employee menu details`: EmployeeMenuPage.tsx, its test,
   EmployeeLessonMenu.test.tsx, e2e/lesson-menu-overlay.spec.ts and this report/STATUS.
   Verify RED, full frontend tests, focused browser tests, types/lint/format/build,
   manual source-backed bowl preview and exact diff. This boundary is complete locally.
2. Eight lesson duplicate occurrences: read actual source bindings and prepare only
   the reviewed draft correction. No published card, Menu item or question deletion.
   Current blocker: accessible Chrome session is Employee; /admin redirects to Employee.
   Second inventoried profile is unavailable to browser control. Requested owner Admin
   session; no draft/publication/rollout was performed.
3. Practice history: diagnose before changing API. FINAL CRA-12 explicitly requires
   current exact-version Latest/Best; practice_results.py also filters history by
   current assessment version and assignment. Missing old results on this screen is
   not proof of deletion. Cross-version presentation is a separate product-contract
   decision; live old-result persistence has not been queried.
4. Final user-path and Linear reconciliation remain pending the content step.

No local commits, index changes, push, deployment, hosted mutation or Linear write
is authorized or claimed by this checkpoint. Existing dirty documentation is preserved.

## Implemented behavior

- Removed the composition section, including known/empty composition presentation.
- One allergen section displays the union of confirmed labels and source labels,
  deduplicated by exact label while preserving order. Source labels are not written
  into confirmed facts; neither source collection is modified.
- Empty lists produce no empty section and no claim of allergen absence.
- Removed date, source heading and unconfirmed-completeness warnings from this UI.
- Kept guest wording, original description disclosure, price, loading/close/focus,
  retry and existing lesson/current-Menu version boundaries.
- No backend, schema, dependency, styling or content change.

## Verification

All commands below ran from frontend with rtk and the existing installed tools.
Direct Node entrypoints avoid pnpm attempting automatic dependency synchronization.

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| RED EmployeeMenuPage regression | 9 | 4 | 0 |
| First combined Menu/lesson run | 16 | 1 | 0 |
| Final full Vitest, 31 files | 153 | 0 | 0 |
| Playwright overlay + lesson structure, 3 viewports | 6 | 0 | 0 |

RED failures demonstrated duplicate Milk and visible composition sections. First
combined run passed all Menu tests; the remaining lesson test expected the removed
warning and was updated to verify the retained description and absent empty section.
The full 153-test gate includes these focused cases; do not sum them.

Commands:

```text
node node_modules/vitest/vitest.mjs run src/employee/EmployeeMenuPage.test.tsx --maxWorkers=1 --reporter=dot
node node_modules/vitest/vitest.mjs run src/employee/EmployeeMenuPage.test.tsx src/employee/EmployeeLessonMenu.test.tsx --maxWorkers=1 --reporter=dot
node node_modules/vitest/vitest.mjs run --maxWorkers=1 --reporter=dot
node node_modules/@playwright/test/cli.js test e2e/lesson-menu-overlay.spec.ts e2e/lesson-structure.spec.ts --workers=1
node node_modules/typescript/bin/tsc -b --pretty false
node node_modules/eslint/bin/eslint.js .
node node_modules/prettier/bin/prettier.cjs --check src/employee/EmployeeMenuPage.tsx src/employee/EmployeeMenuPage.test.tsx src/employee/EmployeeLessonMenu.test.tsx e2e/lesson-menu-overlay.spec.ts
node node_modules/vite/bin/vite.js build
```

Final types, ESLint, scoped Prettier and build passed. The initial type check found
two unsupported Testing Library `exact` options in new tests; removed these options
(string name matching is already exact), then types passed. Initial pnpm invocation
failed before tests with EPERM during automatic install; no dependency change was
made. Elevated direct-tool execution succeeded. No backend/DB/full browser/security
suite was run because production behavior changes only in this shared UI component.

Manual browser: current hosted Food lesson was readable, showing completed state
and the original bowl card. Corrected local production build rendered the bowl
with price 395 UAH, guest text, one list containing all seven existing source labels,
and original description disclosure, without the removed sections/copy. The first
old preview fixture lacked source_note; a separate local-only preview helper now
adds exact key/name/description-matched packaged notes. This is fixture-based visual
verification, not a hosted deployment or recipe confirmation. The reused broad local
lesson proposal is not an accepted content rollout. Local helper under outputs is
excluded from source staging. Preview on loopback port 4176 remains available.

## Review and next step

Fresh diff review confirms only the shared renderer and its three test files change
production/test behavior. Data fields, endpoints, tenant controls and navigation
remain intact. Existing source labels retain their wording; no new ingredient or
allergen inference. git diff --check passed. A follow-up final inventory includes
this report and the STATUS pointer; unrelated existing documentation remains dirty.

Next: obtain the requested Admin session, verify the eight real item bindings, and
prepare a reversible draft correction preserving variants/question links. Publication,
rollout and web delivery require separate explicit authorization under AGENTS.md.
Do not mark CRA-275 Done or claim all daily work completed.

## Admin continuation — 2026-09-25

Denys opened the authenticated Admin session in Chrome profile User 1. The access
blocker above is resolved. Created draft v5 from published v4 through the existing
Admin UI. Fresh readback confirms published v4, draft v5, saved state and unchanged
lesson block counts 45/37/27/39. No block was deleted or changed; no publication or
rollout occurred. This supersedes the earlier no-hosted-mutation checkpoint solely
for creation of the draft copy.

The remaining blocker is item identity in the editor: a rendered menu-card row
contains only the type and payload `{ "note_uk": null }`, with move/delete controls.
Read-only DOM inspection confirms no item name or menu-item binding is exposed in
that row. AdminTrainingPage.tsx renders only block.payload at line 817; the separate
binding is omitted. Do not infer draft identity from old published block UUIDs or
delete anonymous rows by guesswork. Eight removals remain pending.

Next bounded prerequisite: show the bound menu-item name in the Admin lesson editor
and verify it before content deletion. This is additional Admin implementation scope
to reconcile with CRA-275 before editing production code. The existing Employee
polish remains locally verified, unpublished. No application tests were rerun for
this read-only inspection and draft creation; earlier 153/0/0 and 6/0/0 evidence
remains the latest. No Git index, commit, push or deployment changed.
