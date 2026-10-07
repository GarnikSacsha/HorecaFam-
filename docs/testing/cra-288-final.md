# CRA-288 implementation and acceptance

Issue: [CRA-288 — Implement multi-position training, Runner/Bartender content and Academy](https://linear.app/craftspacee/issue/CRA-288/implement-multi-position-training-runnerbartender-content-and-academy).

Branch: `feature/multi-role-training-content`. Authoritative base:
`7a7f6f369aba4c2e0bc38f749615e63645e50e20`. Work was performed in a separate managed
worktree. Original dirty main, other worktrees and Photos were not modified.
No push, PR, merge, deployment or production/staging data change is included.

## Implemented behavior

- Reuses organization OperationalRole positions, separate from Admin/Employee security roles.
  Training supports multiple service/sales/venue-standard modules. Version and module audiences
  can target one/multiple/all positions, including future positions without an enum migration.
  Employee discovery, direct lesson/media access, completion, progress and assessment access
  enforce the current position. Draft copies retain audiences; role changes reconcile assignments
  while preserving history. Rollout previews and confirmation use position-aware requirements.
- Existing Menu/Waiter learning, assessment snapshots, results and authentication are retained.
  The independently approved one-clock auth prerequisite is a separate commit, not a new MFA rule.
- Explicit content-pack import adds Runner (6 units / 15 scenarios), Bartender (6 / 20) and
  shared Service Standards (11 / 10). These are 3 course modules containing 23 ordered lessons,
  with 45 verified generic source scenarios. Shared content targets Waiter, Runner and Bartender.
  Import preserves existing content and leaves Training in Draft. No demo data is in migrations.
- Versioned StandardSets/Rules and pinned module dependencies provide provenance. Deterministic
  candidates enter the existing human review queue. Course knowledge checks use the existing
  question bank, snapshots, device leases and server grading. Correctness/explanation/review is
  unavailable until explicit final submission. Course scores do not invent certification or
  change the existing Final Exam's 20 questions, 70% threshold or retake obligation semantics.
- Existing MenuItem gains optional volume, technique, glassware, garnish, serving standard and
  preparation time. Import, publication, draft copies, partial edits, deltas and audit history
  preserve these fields. Existing ingredients and allergens remain unchanged.
- Academy adds independently published optional articles with category, slug, title, summary,
  plain-text body, order, timestamps, position audiences and private image covers. Reading has
  no required-completion side effect. Thirteen starter articles are explicitly imported as
  Drafts: 4 general and 3 per initial position, without overwriting edits.
- Employee navigation adds Menu/Academy alongside existing Training, Practice and Profile.
  Course checks appear in their module. Existing Admin pages gain only the necessary audience,
  import, preparation and article controls. There is no admin/dashboard redesign.

## Schema and API contracts

| Migration | Change |
| --- | --- |
| 0022_module_position_audiences | Module audiences, all-position flags and multiple non-menu modules |
| 0023_course_assessment_type | Course assessment family and consistent family identity across records |
| 0024_standard_sources | Versioned StandardSets/Rules, module dependencies, source links and immutability |
| 0025_menu_preparation | Nullable validated preparation JSON on versioned MenuItem |
| 0026_academy | Scoped Academy articles/audiences with existing private Asset references |

Migrations are additive or backfill existing family identity without resetting data. Destructive
downgrades refuse populated new content. Only the dedicated local test DB was migrated.
Alembic upgrade/current/check is at 0026_academy with no metadata drift.

New contracts include draft module creation/audience updates and explicit training content-pack
preview/import; standard question generation through the existing Admin question bank; course
attempt start/read/answer/finish/takeover; and Admin Academy list/create/revision update/seed plus
employee list/direct read/protected cover. All endpoints remain under `/api/v1`. Admin writes
reuse MFA/CSRF and appropriate idempotency/revision checks. Article listing is bounded/paginated.

## How to activate the new content

1. In the existing Training editor, open/create the intended Draft and preview the generic pack.
   Map the existing Waiter position if its code differs; review and explicitly import the pack.
2. Review the root and per-module audiences, the existing Menu module and all generic material.
   Confirm local rules separately. Existing Waiter content is not overwritten by the import.
3. Use the current readiness/publication and assignment/rollout workflow. Generate standard
   question candidates, review them and approve through the existing queue. Learners complete
   the required lessons before starting a ready course check.
4. In Academy, choose a location and map three distinct active positions to import 13 Drafts.
   Review/edit each article and explicitly publish it. Future articles can target any positions.

No content was installed or published into a hosted environment by this task.

## Verification

Baseline, established before CRA-288 after the isolated auth fix: backend 996/0/0;
frontend 166/0/0; Playwright 87/0/0. Baseline coverage: statements 94.43%, branches 81.41%,
fixed critical aggregate 89.71%. See [baseline evidence](cra-288-baseline.md).

Final full backend: **1088 passed, 0 failed, 0 skipped** in 2098.19s (34m58s), on the
dedicated local `horeca_test_cra288` database. Same-run independent coverage gates all passed:

| Gate | Covered / total | Result |
| --- | --- | --- |
| Statements | 13411 / 14188 | 94.52% PASS |
| Branches | 2461 / 3018 | 81.54% PASS |
| Fixed critical aggregate | 1335 / 1488 | 89.72% PASS |

Final frontend: **180/0/0** in 34 files (36.58s); Playwright: **96/0/0** (1.5m).
The three full suites total **1364 passed, 0 failed, 0 skipped**.
TypeScript, ESLint, Prettier and production build passed after the review correction.
Ruff format/check passed for 314 files; mypy passed for 285 source files.
Post-suite Alembic upgrade/current/check confirmed `0026_academy` and no metadata drift.
The [Academy checkpoint](cra-288-academy-stage.md)
records RED/GREEN evidence and intermediate failures separately from these final results.

Backend acceptance commands, with test environment variables supplied only to the process:

```text
../.venv/Scripts/python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing --tb=line
../.venv/Scripts/python.exe -m coverage json -o .pytest_cache/cra288/final.json
../.venv/Scripts/python.exe -m tests.coverage_gate .pytest_cache/cra288/final.json
../.venv/Scripts/python.exe -m alembic upgrade head
../.venv/Scripts/python.exe -m alembic current --check-heads
../.venv/Scripts/python.exe -m alembic check
```

Focused evidence and ordered commit boundaries:
[map](cra-288-commit-map.md), [positions](cra-288-position-stage.md),
[assessment](cra-288-assessment-stage.md), [content](cra-288-content-stage.md),
[menu preparation](cra-288-menu-stage.md), [Academy](cra-288-academy-stage.md).
Counts overlap; focused suites must not be added to full-run totals.

## Review boundaries and limitations

Fresh protected-boundary review was separated from implementation and checked the following:

| Protected asset / abuse case | Enforcement and evidence |
| --- | --- |
| Cross-tenant or wrong-position content | Existing active-session authorization, scoped queries and composite FKs; direct lesson/course/article/cover denial regressions |
| Unreviewed or unpublished learning | Draft/publication boundaries, pinned immutable standards and human candidate review; content-pack publication/candidate tests |
| Answer-key disclosure or client scoring | Snapshot-safe attempt responses before finish; backend grading, explicit submission and assessment-family guards |
| Duplicate/stale/concurrent writes | Idempotency fingerprints, revision guards, assignment/attempt locks and device leases; replay, concurrency and takeover tests |
| Private images | Verified existing image upload, same-scope ready Asset, audience check before short-lived URL; linked-asset archival rejection |
| Unsafe article markup | Bounded server fields and plain-text React rendering; literal script-text regression |
| Loss of legacy/new data | Additive migrations, retained history, downgrade refusal and pre/post migration snapshots |

New stored data is educational content, scope/audience identifiers, version/provenance metadata,
course snapshots/results and existing audit records. No new credentials or customer-profile
fields are introduced. Cover images remain private; there is no public bucket/path contract.
This is a scoped implementation review and regression evidence, not a hosted security audit.

- Canonical content is Ukrainian; no restaurant-specific recipe, temperature, timing or
  compensation policy is inferred. Admin review/publication remains explicit.
- The existing location-wide published Menu reference remains intact. Position filtering is
  applied to Training modules and their tests plus Academy; item/category-level Menu ACLs and
  separate simultaneous food/drink Training-menu bindings are not introduced.
- Illustrated menu education reuses private Training images. This branch adds Academy covers,
  not a second public image pipeline or a standalone MenuItem image-management subsystem.
- Standard provenance/publishing supports this bounded pack; a general-purpose standards CMS
  and the separately planned admin redesign are outside this branch.
- Browser tests use mock APIs. They prove UI behavior, not hosted authenticated acceptance,
  real storage delivery or deployment readiness. No new dependencies or paid providers are used.
- The existing large frontend bundle remains (about 573 kB minified); bundle splitting is a
  separate optimization. No credentials, environment files, caches or runtime output are committed.

## Local commits

| Commit | Outcome |
| --- | --- |
| a5184b0 | Isolated session-clock baseline fix and evidence |
| 0ef61b5 | Position-aware modules and assignments |
| 6977fe5 | Standards-backed course checks |
| bd62913 | Runner, Bartender and shared starter content |
| 31f3af0 | Optional preparation fields in the existing Menu |
| fd7b7fb | Optional position-scoped Academy and navigation |
| 5827071 | Review correction: keep inactive article audiences removable |

## Changed-file inventory

The inventory below is generated from the approved base, including the isolated auth prerequisite.
It excludes ignored/runtime files, credentials, dependency installations and the user's dirty main.

<details>
<summary>117 changed files</summary>

```text
STATUS.md
backend/app/api/router.py
backend/app/api/routes/academy.py
backend/app/api/routes/course_assessments.py
backend/app/api/routes/training.py
backend/app/models/__init__.py
backend/app/models/academy.py
backend/app/models/assessments.py
backend/app/models/enums.py
backend/app/models/menu.py
backend/app/models/standards.py
backend/app/models/training.py
backend/app/models/training_assignments.py
backend/app/schemas/academy.py
backend/app/schemas/assessment.py
backend/app/schemas/course_assessment.py
backend/app/schemas/menu.py
backend/app/schemas/menu_history.py
backend/app/schemas/training.py
backend/app/services/academy.py
backend/app/services/academy_catalog.py
backend/app/services/applicability.py
backend/app/services/course_assessments.py
backend/app/services/employee_menu.py
backend/app/services/employee_training.py
backend/app/services/employees.py
backend/app/services/final_exam_attempts.py
backend/app/services/final_exam_configuration.py
backend/app/services/final_exam_readiness.py
backend/app/services/final_exam_results.py
backend/app/services/interactive_answers.py
backend/app/services/interactive_attempts.py
backend/app/services/interactive_history.py
backend/app/services/menu_drafts.py
backend/app/services/menu_history.py
backend/app/services/menu_imports.py
backend/app/services/menus.py
backend/app/services/module_audiences.py
backend/app/services/practice_attempts.py
backend/app/services/practice_results.py
backend/app/services/question_generation.py
backend/app/services/question_review.py
backend/app/services/sessions.py
backend/app/services/standard_questions.py
backend/app/services/training_assets.py
backend/app/services/training_audiences.py
backend/app/services/training_catalog.py
backend/app/services/training_completion.py
backend/app/services/training_content_pack.py
backend/app/services/training_drafts.py
backend/app/services/training_progress.py
backend/app/services/training_publication.py
backend/app/services/training_queries.py
backend/app/services/training_rollouts.py
backend/migrations/versions/0022_module_position_audiences.py
backend/migrations/versions/0023_course_assessment_type.py
backend/migrations/versions/0024_standard_sources_standard_sources.py
backend/migrations/versions/0025_menu_preparation.py
backend/migrations/versions/0026_academy_academy.py
backend/tests/api/test_academy_api.py
backend/tests/api/test_course_assessments.py
backend/tests/api/test_menu_preparation.py
backend/tests/api/test_position_training_api.py
backend/tests/api/test_standard_question_admin_api.py
backend/tests/api/test_training_audience_api.py
backend/tests/api/test_training_content_pack.py
backend/tests/factories/assessments.py
backend/tests/integration/test_assessment_family_security.py
backend/tests/integration/test_course_assessment_models.py
backend/tests/integration/test_position_training.py
backend/tests/integration/test_session_clock.py
backend/tests/integration/test_standard_sources.py
backend/tests/migration/test_academy_menu.py
backend/tests/migration/test_course_sources.py
backend/tests/migration/test_migrations.py
backend/tests/unit/test_standard_questions.py
docs/testing/README.md
docs/testing/cra-288-academy-stage.md
docs/testing/cra-288-assessment-stage.md
docs/testing/cra-288-baseline.md
docs/testing/cra-288-commit-map.md
docs/testing/cra-288-content-stage.md
docs/testing/cra-288-final.md
docs/testing/cra-288-menu-stage.md
docs/testing/cra-288-position-stage.md
frontend/e2e/academy.spec.ts
frontend/e2e/course-assessment.spec.ts
frontend/e2e/training-slice.spec.ts
frontend/src/admin/AdminAcademyPage.test.tsx
frontend/src/admin/AdminAcademyPage.tsx
frontend/src/admin/AdminAuditPage.tsx
frontend/src/admin/AdminMenuPage.test.tsx
frontend/src/admin/AdminMenuPage.tsx
frontend/src/admin/AdminPositionModuleForm.tsx
frontend/src/admin/AdminQuestionBankPage.test.tsx
frontend/src/admin/AdminQuestionBankPage.tsx
frontend/src/admin/AdminTrainingAudiencePanel.test.tsx
frontend/src/admin/AdminTrainingAudiencePanel.tsx
frontend/src/admin/AdminTrainingContentPack.tsx
frontend/src/admin/AdminTrainingPage.test.tsx
frontend/src/admin/AdminTrainingPage.tsx
frontend/src/api/assets.ts
frontend/src/api/contracts.ts
frontend/src/app/App.tsx
frontend/src/employee/EmployeeAcademyPage.test.tsx
frontend/src/employee/EmployeeAcademyPage.tsx
frontend/src/employee/EmployeeCourseAssessment.tsx
frontend/src/employee/EmployeeLearningModulePage.tsx
frontend/src/employee/EmployeeLearningPages.test.tsx
frontend/src/employee/EmployeeMenuPage.test.tsx
frontend/src/employee/EmployeeMenuPage.tsx
frontend/src/operator/OperationsPages.test.tsx
frontend/src/shells/AdminShell.tsx
frontend/src/shells/EmployeeShell.tsx
frontend/src/shells/Shells.test.tsx
frontend/src/styles.css
frontend/src/ui/MenuPreparation.tsx
```

</details>

LOCAL ACCEPTANCE: PASS. Implementation and the mapped automated verification are complete.
Ready for human review; hosted acceptance and any delivery action remain separate steps.
No push, PR or merge is authorized or performed.
