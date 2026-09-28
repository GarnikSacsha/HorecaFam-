# CRA-275 reconciliation and student acceptance — 2026-09-24

## Current continuation — 2026-09-25

[Menu polish, approved Admin identity extension and task checklist](menu-detail-polish-2026-09-25.md)
supersede the remaining-action wording below. Published v4 remains active; an unchanged
draft v5 now exists. Eight duplicates remain pending live binding verification after
frontend delivery. Preserve the historical evidence and version-specific IDs below.

## Scope and authority

Denys authorized the audit follow-up, existing Menu/lesson usability work and student-side tests.
No new feature, dependency, architecture, unrelated refactor or task expansion.
Current bounded issue: CRA-275. Wider operational acceptance remains CRA-122.

Ordered work boundaries, declared before editing:
1. Reconcile current source/delivery/contract evidence: STATUS.md, CONTEXT.md,
   docs/testing/README.md, this report and the two September 23 lesson/rollout reports;
   verify Git/Railway/browser evidence, links and diff. Intended future boundary:
   docs: reconcile delivered lesson experience and acceptance.
2. Verify student lesson/Menu/Interactive/Practice/history through the existing UI;
   record exact results and content mismatches here. Any behavior correction needs
   its own failing regression before production changes. Any content publication
   needs an exact preview preserving source links and separate publication approval.
No local commits, push or new deployment are authorized by this work map.
Documentation-only TDD exception: source/readback/link/diff verification replaces RED.

## Verified baseline

- Active workspace: registered worktree 5c12, branch codex/cra-275-lesson-category-ux.
- HEAD and direct GitHub main: 60bf1599324040e62c5cea12725df17d111cdb50.
- API deployment: 0aefad8b-aed6-456e-9e1c-35b637f3272e; web:
  db15b2c1-55d5-47c6-aae8-d1132936716c; both SUCCESS on the same commit/main.
- Existing API/web source is GarnikSacsha/HorecaFam-. Source connection/delivery
  were already completed; do not repeat older preparation instructions.
- Old main@4b45108 is five commits behind and has inherited mixed changes.
  Old 6b30@7cffa59 also retains previous work. Neither was overwritten.
- Saved September 23 rollout delivery evidence records two employees moved to v3
  with 100% and 0% progress preserved and panel survival after reload.
- Fresh Employee UI confirms v3, 4/4 completions, 100% progress, certification,
  Final 20/20 (September 22) and 19/20 (September 17).
- All five cron services have no deployment or schedule. Worker has an older
  separately delivered artifact. These are open CRA-122 gates, not Menu blockers.

## Fresh audit checks from this session

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend unit: source notes, Final quotas, authored contract | 20 | 0 | 0 |
| Frontend: lesson structure, Menu overlay, Admin Training | 20 | 0 | 0 |
| Public HTTP GET smoke | 6 | 0 | 0 |

Frontend initially failed before collecting tests because sandbox prevented child
process startup; elevated rerun passed without dependency or code changes.
HTTP helper initially had a PowerShell syntax error; corrected read-only execution
returned 200 for healthz, API health, home/login and 404 for unknown API/missing asset.
Git diff --check passed in all three reviewed worktrees.
Full backend/PostgreSQL coverage, complete browser suite and a security scan were
not rerun. Prior 979/147/84 and 150-test reports remain dated overlapping evidence.

## Current content findings

The delivered reader supports heading-based contents and assignment-bound named
cards. That does not create category blocks in existing Published Training.
Food v3 begins with a retained lemonade review card, then selected Food cards;
no category-heading contents is rendered. Its retained text says five questions
while the implemented cycle permits up to five. The 308-item/32-category local
proposal is not proof those contents are published.

Source-only composition/allergen annotations stay unverified. Empty annotations
are not absence of allergens. Inline lesson cards use the assigned Menu snapshot;
the modal uses the existing current-Menu endpoint. Preserve that version boundary.

## Linear reconciliation

Updated the existing descriptions of CRA-272/274/275 and START HERE with current
delivery evidence; acceptance states were preserved. Consolidated already delivered
CRA-272/275 additions in FINAL CRA-12: authored candidates, curated Final quotas,
source_note, assignment-bound lesson summaries/module_id and persisted rollout_id.
No new contract behavior or message/comment was created by the reconciliation.

## Student verification continuation

The direct request authorizes using the existing student session for a bounded
lesson test and Practice check. Such tests create ordinary attempts/results and
must be distinguished from the owner's knowledge assessment. Do not force a new
Final Exam on an already certified employee or issue a retake. Preserve all history.


## Completed student acceptance — September 24

These are agent technical checks in Bacara Demo, not Denys's knowledge assessment.
Three ordinary completed attempts were created through the existing Employee UI:

| Flow | Result | Evidence |
| --- | --- | --- |
| Dessert Interactive, first batch | 4/5, 80% | One deliberate wrong vanilla-eclair answer; correct answer and explanation appeared after confirmation |
| Dessert Interactive, remaining batch | 3/3, 100% | Three remaining questions, no repeat across the eight-question cycle |
| Practice | 10/10, 100%, zero critical errors | Ten distinct questions; saved two answers, reloaded, resumed at question three; feedback hidden until finish |

After cycle exhaustion, explicit restart restored eight available questions without
automatically starting another attempt. Existing attempt history remained visible.
Practice result survived a reload. After all tests Home still showed Training v3,
4/4 completion and certification September 17. Final history remained 20/20
September 22 and 19/20 September 17. No Final attempt or retake was created.

Additional automated verification, current source 60bf159:

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Full frontend Vitest, 31 files | 151 | 0 | 0 |
| Playwright lesson structure and Menu overlay, three viewports | 6 | 0 | 0 |

Commands: `node node_modules/vitest/vitest.mjs run --maxWorkers=1 --reporter=dot`;
`node node_modules/@playwright/test/cli.js test e2e/lesson-structure.spec.ts e2e/lesson-menu-overlay.spec.ts --workers=1`.
Both ran from frontend through rtk; approved elevated execution was needed for browser/process startup.
The earlier focused 20 frontend checks overlap the full 151 and must not be summed.

## Minimal content correction preview — not an API payload

Fresh Employee DOM inventory: Food 31 cards, Dessert 20, Other 15, Drinks 23.
All four have no content category headings; only confirmation/Interactive headings.
All four retain the conflicting five-question introduction.
No new lesson, feature, menu item, question, source annotation or 308-card expansion.

Replace the introductory sentence in all four:

- Before: «Після читання пройдіть інтерактив із п’яти питань. Пояснення відповідей спираються на цю версію меню.»
- After: «Після читання пройдіть інтерактив: до п’яти питань за одну спробу. Пояснення відповідей спираються на цю версію меню.»

Card positions below are one-based positions in the September 24 published Employee view,
not editable block IDs. Keep each card's associated text/variant blocks with that card.
Keep lesson identities, question/source links, read acknowledgements and assessment history.

| Lesson | Proposed order of existing card positions | Category headings |
| --- | --- | --- |
| Food | 2–31, then 1 | Стартери (2–7), Сніданкові сніданки (8–16), Хелсі-сніданки (17), Супи (18–20), Салати (21–23), Млинці (24), Сендвічі та бургери (25–26), Боули (27–29), Щось особливе (30), Кідс меню (31), Повторення (1) |
| Dessert | 13–20, then 1, then 2–12 | Десерти; Морозиво Maropu; Повторення |
| Other | 1–3, 10–11, 6–9, 12–13, 14–15, then 4–5 | Б/а коктейлі; Натуральне вино — келихами; Літні коктейлі; Морозиво Maropu; Повторення |
| Drinks | 1–10, 12–19, 23, then 20–22, then 11 | Сезонні напої; Кава; Повторення |

Visible duplicate candidates, not yet proven identical source blocks:

- Other: positions 2/10 «Коктейль б/а Gin&Tonic» and 3/11 «Коктейль б/а Pineapple Gin&Tonic».
- Drinks: 1/12 «Матча-клауд», 2/14 «Айс-матча яблуко-алое»,
  3/13 «Айс-матча-полуниця», 5/23 «Айс-матча гранат-полуниця»,
  6/15 «Крем-сода», 7/16 «Крем-сода ягідна».

Before removal, compare Admin source IDs, variant companions and linked questions.
If truly identical and unneeded for a separate source/variant, retain one copy with
all required links: Other would become 13 visible cards and Drinks 17.
The reorder preview above deliberately preserves every occurrence until that check.

## Remaining boundary

An Admin-content read attempt in the in-app browser redirected to Employee Home.
The other known Chrome session is Platform Operator; no authenticated Admin editor
is available. Consequently block IDs, exact current draft revisions and companion
blocks could not be safely resolved. This preview is reviewable at the visible-content
level but is not falsely represented as an import-ready payload or a published fix.

Next bounded step: open an authorized Admin session, map this preview to the existing
published version and verify duplicate identities, then preview the exact content revision.
Publishing/rollout requires separate authorization under repository AGENTS.md.
No need to redeploy unchanged application code. No broader feature or extra issue is needed.


## Applied draft correction — 2026-09-24 continuation

Denys requested continuation after the concrete minimal-content preview.
Chrome profile 2 now had authenticated Admin access to Bacara Demo; the earlier
Admin-access blocker is resolved. The existing published v3 had no draft.
Created draft v4 through the existing Admin UI and prepared the four existing lessons.

| Lesson | Cards before / after | Blocks after | Heading blocks |
| --- | ---: | ---: | ---: |
| Food | 31 / 31 | 45 | 11 |
| Dessert | 20 / 20 | 37 | 3 |
| Other | 15 / 15 | 27 | 5 |
| Drinks | 23 / 23 | 39 | 3 |

Applied the positional preview above, including variant companion blocks.
Added 22 category/review headings; moved the existing review material behind the main
material; replaced the conflicting introduction with the exact up-to-five sentence
in all four lessons and placed it at the end. No cards or questions were added.
No existing Menu-card block was deleted or recreated. The four obsolete general
instruction text blocks were replaced in the draft; published v3 remains unchanged.

Duplicate candidates were retained. The current Admin editor renders card payloads
without their separate menu_item_id or a human-readable item name; identical visible
payloads do not prove identical source/variant identity. Category/card alignment was
based on the already verified Employee v3 order and preserved positional moves.
Deleting eight candidate duplicate occurrences is not claimed as completed.

Fresh readback after a full page reload:
- All four lessons reopened successfully with exact card/block/heading counts above.
- All four contain exactly one corrected instruction, no old five-question wording.
- Complete visible block payload/order comparison passed for Food, Dessert and Other;
  Drinks was checked during its reorder and its headings/counts/copy were rechecked
  after reload. Existing variant texts and review notes were retained.
- Readiness shows «Готово», publication button enabled, zero UI error alerts.
  Existing Ukrainian-fallback warnings for missing English translations remain.
- Employee Home still shows assigned v3, 4/4 completion, 100% and certification.
- No new attempts, Final Exam, retake, publication or employee rollout occurred.
- Automated code suites were not rerun for this content-only continuation. The
  earlier 151 Vitest / 6 Playwright results remain the latest code evidence.

Execution notes: initial browser helper comparisons had object-key ordering and
stale-closure problems; the actual UI readbacks matched the saved moves. A long UI
batch timed out and reset its control session; the saved Food order was recovered
from a fresh page inventory. Short batches with state/readback checks completed.
Fast-click attempts hit browser-action timeouts; uncertain actions were inspected
before continuing. These were tooling interruptions, not claimed application-test
failures. All final readbacks above passed.

Publication was prepared in the existing confirmation dialog. Automatic approval
review rejected the final confirmation because an explicit separate publication/
rollout authorization was missing. No workaround or retry was attempted.
The dialog was canceled; verified published v3 and draft v4 remain.
Denys was asked explicitly to authorize publishing v4 and transferring the two
existing employees with completed lessons/results/certification preserved.
Next action after that authorization: publish this saved draft once, review the
v3-to-v4 rollout preview, preserve completion for changed lessons, confirm the
two-employee forecast, execute once, then verify all four Employee lesson pages,
Menu overlay, progress and immutable Final history. No code deployment is needed.

Repository changes in this continuation are STATUS.md and this report only.
The existing six-document selective documentation boundary remains unchanged;
no index, commit, push, dependency, production source or API-contract change.


## Published v4 and assessment recovery — 2026-09-24

Denys explicitly authorized publication and the two-employee transfer ("Можно делать"). Training v4 was published through Admin. For all four changed lessons, preserve-completion decisions were selected and the preview refreshed before confirmation: employee forecasts remained 4/4 (100%) and 0/4 (0%). Transfer completed and survived reload.

Employee v4 readback passed for all four lessons: Food 31 cards/45 blocks, Dessert 20/37, Other 15/27, Drinks 23/39; all 89 card occurrences preserved, category/review headings and corrected up-to-five wording present. Drinks contents anchor navigated to Coffee; named card overlay opened and closed successfully.

Post-publication checks exposed ASSESSMENT_NOT_CONFIGURED: publication does not copy question bindings. Recovered using the existing Admin authored-import workflow and unchanged outputs/cra-272-preparation/content/ui-import.json from worktree 6b30 (60 questions: food 30, drinks 12, desserts 8, other 10). Source/lesson matching passed; 60 candidates created and approved for v4. Published Final with the existing 10/4/3/3 quotas and 70% threshold. No template generation or new question content was introduced.

Fresh Admin reload confirms 4/4 lessons available, Practice ready 60/10, Final ready 60/20. Dessert retains its expected limited-rotation warning (8 questions); other pools are 30/12/10. Employee Drinks shows 12 new questions and Start; Practice shows Start. Home confirms assigned v4, 4/4 and certification; Final still shows 20/20 September 22 and 19/20 September 17. No new test attempt or certification was created in this continuation. Practice history is scoped to current assessment version in practice_results.py, so the previous v3 Practice result is not displayed on v4; its persistence was not independently queried. Do not claim cross-version Practice history acceptance.

No application code, dependency, migration, deployment, Git index or commit changed. Prior automated evidence remains 151 frontend and 6 browser checks passed; these were not rerun for the content publication. Remaining: eight retained duplicate-card candidates require identity review; no broad content expansion is authorized.

Additional readback: expanded Dessert attempt history retains prior-version attempts, including September 24 results 3/3 and 4/5; also September 23 2/3, September 22 5/5 and September 17 4/5. CRA-275 updated with this checkpoint. Final git diff --check passed (line-ending warnings only).


## Eight duplicate-card pairs reviewed — 2026-09-24

Read-only follow-up on published v4. All eight pairs have equal visible card text and equal fully loaded Menu dialogs (name/category/price/guest text/source state); an initial premature comparison captured loading states and was discarded. The final comparisons explicitly waited for each item heading: 8/8 equal, 0 unequal. Each first occurrence retains the original variant companion; no second occurrence has a variant companion or a repeat note. The source menu-cards.json contains one source item and one variant per name. The unchanged authored-import packet contains one question per name. This confirms redundant visible presentation, not a live database UUID equality check: menu_item_id is not exposed by the rendered card or current Admin payload display.

| Lesson | Item | Source ID | Keep v4 card position | Redundant v4 card position | Redundant block UUID |
| --- | --- | --- | --- | --- | --- |
| Drinks | Матча-клауд | 1720026 | 1 | 11 | d4a80d32-5079-4cc1-a2b2-9ba53c76eae3 |
| Drinks | Айс-матча яблуко-алое | 1720027 | 2 | 13 | b6a039c8-95dd-42dd-9dc9-7abf0f86181a |
| Drinks | Айс-матча-полуниця | 1887140 | 3 | 12 | 2ba02016-51ad-4bc2-b429-64ef876c23d8 |
| Drinks | Айс-матча гранат-полуниця | 560651 | 5 | 19 | 66b81055-6f63-49cc-b267-15d843147d01 |
| Drinks | Крем-сода | 968565 | 6 | 14 | 631dda6b-b6ac-4afb-ae47-a3d33874609b |
| Drinks | Крем-сода ягідна | 1720029 | 7 | 15 | 474381fa-bf4a-41af-a2bd-d6c5bef79d9e |
| Other | Коктейль б/а Gin&Tonic | 1521118 | 2 | 4 | a8834884-43b1-47f0-b9a5-625c884dd53f |
| Other | Коктейль б/а Pineapple Gin&Tonic | 1521119 | 3 | 5 | 74294ac0-16c1-4dbe-8e8e-1e1d0765a902 |

Recommended bounded correction after actual item bindings are verified: remove only these eight redundant occurrences in a new draft, retaining the first cards and every variant companion. Expected visible cards: Drinks 23→17, Other 15→13, total 89→81; Food31 and Dessert20 unchanged. These IDs refer to published v4; a cloned draft receives new IDs and must be remapped. Do not remove Menu items or questions. Publication/rollout must include assessment readiness recovery before student acceptance, as demonstrated above.

No draft created, hosted content changed, question/attempt started, production source edited, or Git index/commit changed in this review. Automated application tests were not rerun for a read-only content comparison. This report is the only local file changed in this follow-up.
