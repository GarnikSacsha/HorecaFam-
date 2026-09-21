# HoReCa source and acceptance reconciliation — 2026-09-21

## Local commit execution — later September 21 checkpoint

Denys subsequently authorized local commits under the four-entry map below. The prior
preparation-only and uncommitted statements are historical as of that authorization.

| Map entry | Local checkpoint | Paths |
| --- | --- | --- |
| CRA-237 demo publication | `25917f2` | Exact 12 mapped paths |
| CRA-238 bound menu picker | `381c288` | Exact six mapped paths |
| CRA-240 readiness isolation | `62b0144` | Exact four mapped paths |
| CRA-122 documentation reconciliation | This documentation checkpoint | Exact 14 mapped paths |

No push, deployment, history rewrite, dependency or product-behavior change was performed.
The verified remote baseline remains `9d68d9d`; owner acceptance remains separate from commits.
Photos, outputs and other worktrees remain outside the map.

The sole source-file edit during commit execution was Prettier normalization of 662 CRLF
line endings to LF in `frontend/src/admin/AdminTrainingPage.test.tsx`. The before/after text
is identical after newline normalization, so no new RED test is appropriate. The direct local
Prettier executable was used after `pnpm exec prettier` could not resolve the command; no
dependency was installed. Global format check, lint and typecheck pass. A fresh focused Vitest
run passed 16 tests in two files, zero failed/skipped. These overlap the earlier 128 tests.

Before staging, the 399-file snapshot and sealed candidate/ZIP validation passed again.
All earlier behavior checks in this session apply to unchanged implementation content;
they were not needlessly repeated. The line-ending-only edit preserves the candidate's
documented CRLF/LF-normalized source equivalence. Each commit's selective inventory and
staged whitespace check were verified. The ordered map below is the executed map, not
authorization to perform a second round of commits.

Final documentation validation: 14 mapped documents, 262 relative links, zero missing targets
and zero matches for the checked credential/private-key/database-URL or absolute user-path
patterns. All 399 candidate source and ZIP hashes still match. Of 399 snapshotted files,
398 remain byte-identical and the one test differs only in line endings. Four Linear issues
and three navigation documents were updated and read back; previous content and all issue
acceptance states are preserved.

## Scope and authority

Denys requested the read-only audit and then authorized completing the follow-up work that
does not require his participation. CRA-122 owns this documentation, local verification and
delivery-preparation step. Existing CRA-237/238/240 and CRA-234 behavior is inspected, not changed.
No new product contract, dependency, migration, provider setting, hosted data or question-bank
operation is introduced. Issue acceptance states are preserved.

Documentation-only TDD exception: source reads, evidence reconciliation, relative-link checks,
exact diff/inventory and safe-content checks replace a new RED test. Existing RED records remain
in the individual implementation reports. The reruns here are GREEN verification, not new TDD.

Ordered documentation checkpoint map, defined before editing:

1. `docs: reconcile current source delivery and acceptance`: this report, `STATUS.md`,
   `README.md`, `CONTEXT.md`, `docs/testing/README.md`. Gate: source/status matrix, explicit
   historical boundaries, valid relative links, no unsupported acceptance claims.
2. `docs(deploy): prepare bounded CRA-234 delivery`: `docs/deployment/security-fixes-cra-234-delivery.md`.
   Gate: verified baseline archive, six-file overlay, manifest and archive parity, unchanged
   migrations/frontend/dependencies, focused verification and exact rollback boundary.
3. Synchronize current navigation in Linear START HERE, the demo path, Stage 2 and affected
   issues; read back each update. No state transition or new implementation authorization.

These are preparation boundaries, not permission to stage, commit, push or deploy. Local helper
scripts, manifests and archives remain under excluded `outputs/`; Photos and other worktrees
are untouched. No new product code or test change is part of this checkpoint.

## Source and delivery matrix

Fresh read-only Git evidence from the audit in this session: local `main`, cached `origin/main`
and direct remote `refs/heads/main` all equal `9d68d9d6d231583f838a5921067ad435e418e08d`.
The index is empty. The worktree initially has 22 modified tracked files plus existing untracked
tests/reports/picker files, Photos and outputs. Global Harness local HEAD equals the pinned
`3eaa9586b4e09e70399c2600aa1808b18449a15d`; no upstream remote refresh is claimed.

| Boundary | Git source | Recorded hosted evidence | Remaining gate |
| --- | --- | --- | --- |
| CRA-271 demo UX/history | Six commits ending at `9d68d9d`, published | September 17 API/web delivery and schema 0020 | Done in Linear; old question bank deliberately unchanged |
| CRA-237 grouped findings/demo publication | Implemented but uncommitted | Delivered and Menu published; preserved by CRA-271 | Selective source checkpoint and owner acceptance; full fact editor is separate |
| CRA-238 bound menu picker | Implemented but uncommitted | Delivered; used for four lessons, then Training published | Selective source checkpoint and owner acceptance |
| CRA-240 lesson-readiness family isolation | Implemented but uncommitted | Delivered; three readiness reads recovered; preserved by CRA-271 | Selective source checkpoint and owner acceptance |
| CRA-234 recovery/body limits | `3b3c79a` and `0f767a6` are ancestors of published HEAD | Explicitly excluded from CRA-271 delivery | Prepared candidate, separate rollout and acceptance |
| CRA-239 question review/publication | Operational task, no application change | 80 reviewed questions published; four lessons ready | Formal acceptance distinct from the completed publication |
| CRA-122 staging | Mixed service source history | API/web and worker have recorded delivery evidence | Full staging gates and owner decision remain open |

Historical counts: Menu has 308 items, Training four required lessons, and the approved bank
covers 27 distinct source items. The September 17 owner-reported Employee/mobile/password-reset
check and 19/20 Final Exam supersede older statements that no Employee journey occurred.
CRA-271 subsequently recorded authenticated certified Home and persisted Results reads.
These are dated evidence, not a new authenticated session or Alexandra's venue sign-off today.

Do not recreate accounts, resend invitations, reimport Menu, repeat Training publication or
regenerate the existing question bank because an older section lists those as next actions.

## Reproducibility check

The original CRA-271 `source-verified.json` contains 397 files. All 397 stored source hashes
match; no extra files exist. Its ZIP SHA-256 matches the deployment report:
`6aeb978e3f1678ac7b11b70f2060c323c4264f5fc651e4a3ef09bb750478759a`.

Comparing that source to the current working tree and normalizing only CRLF/LF shows exactly
five existing-file content differences: `backend/README.md`, `backend/app/main.py`,
`backend/app/services/password_recovery.py`, `backend/tests/api/test_password_recovery.py`,
and `backend/tests/api/test_rate_limit_capacity.py`. The two additional tracked source files
are `backend/app/core/request_body.py` and `backend/tests/api/test_request_body_limit.py`.
No baseline path is missing. This explains the different delivered/Git compositions without
assuming a plain checkout of HEAD reproduces staging.

The prepared CRA-234 candidate keeps the original 397-file source and overlays only six
immutable source/test files from HEAD, adding two paths for 399 files total. All 396 non-Markdown
files equal the working-tree files after CRLF/LF normalization. The three Markdown files remain
the baseline packet's documentation and are not current status authority. Candidate hashes,
scope and later execution checks are in the [delivery plan](../deployment/security-fixes-cra-234-delivery.md).

## Verification ledger

Commands run from the corresponding backend/frontend directory using `.harness/TESTING.md`.
PostgreSQL runs load the ignored test configuration without printing it and require `APP_ENV=test`
plus a dedicated `horeca_test` database. The existing test fixtures alone manage test schema/data.

| Check | Current result |
| --- | --- |
| Combined backend publication/import/Menu/readiness/recovery/history/generation selection | 125 passed, 0 failed, 0 skipped; 296.16 seconds, real dedicated PostgreSQL |
| Full Vitest, `rtk pnpm test --maxWorkers=2` | 128 passed in 28 files, 0 failed, 0 skipped |
| Playwright menu demo and picker, `--workers=2` | 6 passed, 0 failed, 0 skipped; desktop/compact/mobile, synthetic API |
| Ruff format/check | Passed; 267 files formatted |
| Strict mypy `app tests` | Passed; 244 source files |
| Frontend lint and typecheck | Passed |
| Frontend production build | Passed; JS `index-B5fENSqR.js`, CSS `index-BiyR8wr3.css` match the recorded delivered asset names; existing 500 kB chunk warning |
| Global frontend format check | Failed: existing `src/admin/AdminTrainingPage.test.tsx` formatting; file preserved |
| Public HTTP in preceding audit this session | 4 passed, 0 failed/skipped: `/healthz`, `/api/v1/health`, `/`, `/login` |

The earlier audit's 24 backend and 20 frontend tests overlap these selections; do not add them
to the totals. Sandbox initially blocked the audit's frontend Vite startup; the approved rerun
passed. The combined follow-up frontend run started directly with the required execution access.
No full backend coverage, full Playwright suite, Docker build, authenticated hosted acceptance,
live recovery stress, email send or hosted schema check was performed by this reconciliation.

Backend selection (125 collected):

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_menu_publication_api.py tests/api/test_menu_import_api.py tests/api/test_menu_admin_api.py tests/api/test_employee_menu_api.py tests/integration/test_interactive_training_readiness.py tests/integration/test_assessment_family_security.py tests/api/test_assessment_admin_api.py tests/api/test_password_recovery.py tests/api/test_rate_limit_capacity.py tests/api/test_request_body_limit.py tests/integration/test_password_reset_delivery.py tests/integration/test_database.py tests/integration/test_menu_change_history.py tests/unit/test_question_generation.py tests/unit/test_question_review.py -vv -p no:cacheprovider --tb=no --show-capture=no
```

Browser selection:

```powershell
rtk pnpm test:e2e menu-demo-publication.spec.ts training-menu-picker.spec.ts --workers=2
```

## Exact future selective source checkpoints

No staging or commit is performed. Review the diff anew before executing this map; its starting
HEAD is `9d68d9d`. Do not recreate CRA-234 or CRA-271 commits that already exist in ancestry.

1. **CRA-237 coherent implementation — `feat(menu): support explicit non-production demo publication`.**
   Paths: `backend/app/api/routes/menus.py`, `backend/app/schemas/menu.py`,
   `backend/app/services/menu_publication.py`, `backend/tests/api/test_menu_publication_api.py`,
   `frontend/src/admin/AdminMenuLifecyclePanel.tsx`,
   `frontend/src/admin/AdminMenuLifecyclePanel.test.tsx`, `frontend/src/admin/AdminMenuPage.tsx`,
   `frontend/src/api/contracts.ts`, `frontend/src/styles.css`,
   `frontend/e2e/menu-demo-publication.spec.ts`, `docs/testing/menu-demo-publication-cra-237.md`,
   `docs/testing/menu-fact-confirmation-workflow.md`.
   Gate: publication/import/Admin/Employee API and generation checks, lifecycle/page Vitest,
   demo Playwright, Ruff/mypy, lint/types/build and exact diff review. Keep the UI and additive
   server capability together to avoid an intermediate frontend/backend mismatch.
2. **CRA-238 picker — `feat(admin): select training menu cards by name`.**
   Paths: `frontend/src/admin/AdminTrainingMenuPicker.tsx`,
   `frontend/src/admin/AdminTrainingMenuPicker.test.tsx`, `frontend/src/admin/AdminTrainingPage.tsx`,
   `frontend/src/admin/AdminTrainingPage.test.tsx`, `frontend/e2e/training-menu-picker.spec.ts`,
   `docs/testing/training-menu-picker-cra-238.md`.
   Gate: picker/editor tests, three-viewport picker Playwright, lint/types/build; resolve the
   explicitly identified formatting difference within this checkpoint before declaring its
   full formatting gate green. No audience/recovery redesign belongs here.
3. **CRA-240 readiness — `fix(assessment): isolate interactive lesson readiness`.**
   Paths: `backend/app/services/question_review.py`,
   `backend/tests/integration/test_interactive_training_readiness.py`,
   `docs/testing/interactive-training-readiness-cra-240.md`,
   `docs/deployment/readiness-fix-cra-240.md`.
   Gate: four PostgreSQL regressions and adjacent family/Admin checks, Ruff/mypy and diff review.
4. **CRA-122 evidence — `docs: reconcile delivered demo and pending security rollout`.**
   Paths: `README.md`, `CONTEXT.md`, `STATUS.md`, `backend/README.md`,
   `docs/architecture/README.md`, `docs/testing/README.md`,
   `docs/deployment/cra-122-source-build-preparation.md`,
   `docs/deployment/staging-acceptance-cra-122.md`, `docs/deployment/staging-cra-122.md`,
   `docs/deployment/staging-preflight-2026-09-12.md`, `docs/deployment/demo-ux-cra-271.md`,
   `docs/testing/demo-continuation-2026-09-16.md`, this report and the CRA-234 delivery plan.
   Gate: each accumulated documentation hunk reviewed, links/content/inventory checked,
   Linear readback. STATUS shared evidence is intentionally collected in this final checkpoint.

Photos, outputs, environment files, caches, generated artifacts and other worktrees are excluded
from every checkpoint. These path sets cover the initial uncommitted source/docs inventory plus
this task's two new reports; they do not authorize unrelated changes arriving later.

## Remaining acceptance and next product boundary

- CRA-237/238/240: delivery evidence exists; preserve In Progress until their required owner
  acceptance is explicit. A passing local rerun is not a substitute for that decision.
- CRA-239: publication is complete; CRA-271 records a later Employee result. Reconcile acceptance
  against those records rather than repeating operational writes.
- CRA-234: source is published, candidate is prepared, hosted correction remains unperformed.
- CRA-122: verify current worker/source and suspended cron state at action time; complete the
  approved real-origin auth/tenant/lease/retry/cron/storage evidence under bounded execution.
  A delivered invitation is recorded; this is not proof of all provider retry/idempotency gates.
- Pilot load, backup/PITR/asset recovery and physical accessibility/venue UAT remain separate
  CRA-78 stages. Do not mark CRA-122 or the pilot Done from public health or demo success.
- Next product proposal: [source-based Menu fact confirmation](menu-fact-confirmation-workflow.md).
  Alexandra supplies evidence; unknown facts stay unknown. The new issue must settle domain-specific
  provenance storage before a migration is proposed. The current name/price editor and manual-create
  defaults must not be presented as a completed fact-review workflow.
- Existing questions keep old choices; a smaller-choice bank requires separately reviewed
  generation/publication. Business history covers new manual Draft CRUD, not historical reconstruction,
  import/publication events or email digests.

## Linear readback and final inventory

Updated the current checkpoint in CRA-122/237/238/240/234/239 and the three navigation documents:
START HERE, Two-person MVP demo, and CRA-122 Stage 2. Each issue remains In Progress; CRA-271
remains the existing Done reference. Previous content is preserved below the new checkpoint.
Readback normalizes Linear's automatic issue mentions and Markdown code formatting; it does
not ignore changes to the substantive text. Linear initially converted an issue identifier inside
the delivery-report filename into a mention; the path was corrected to literal inline code.
No comments/messages, assignments, issue creation, acceptance transition or contract edit occurred.

Final local verification: all 399 snapshotted backend/frontend source/test/document files are
unchanged by this task. The six documentation deliverables contain 177 valid relative links,
zero missing targets, and no matches for the checked credential/private-key/database-URL or
absolute user-path patterns. The candidate source and ZIP both contain exactly the 399 manifest
paths with matching hashes; exactly the six declared CRA-234 paths differ from the baseline.
Git whitespace check passes and the index remains empty.

Files authored/edited by this follow-up: `README.md`, `CONTEXT.md`, `STATUS.md`,
`docs/testing/README.md`, this report, and `docs/deployment/security-fixes-cra-234-delivery.md`.
Untracked local preparation scripts and manifests live in `outputs/reconciliation-2026-09-21/`;
the sealed candidate lives in `outputs/cra-234-delivery-preflight-2026-09-21/`. They are excluded
from every proposed commit. Existing dirty source/docs, Photos and other worktrees are preserved.

Next owner-facing decisions are now concrete: authorize the reviewed selective commit map
(with the CRA-238 test-formatting gate still explicitly open), or authorize the bounded CRA-234
API delivery after an action-time baseline check. Neither action is inferred from this preparation.
