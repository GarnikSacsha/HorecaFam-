# MVP Vertical Slice 4 — Assignment, Completion and Rollout acceptance

**Bounded issue:** [CRA-57](https://linear.app/craftspacee/issue/CRA-57)  
**Canonical plan:** [CRA-56](https://linear.app/craftspacee/issue/CRA-56)  
**Acceptance date:** 2026-08-29  
**Status:** accepted and fast-forward published through `d4e0184`

This record maps the accepted 26-scenario Slice 4 gate to evidence that actually ran. It does not
replace the Linear contracts and makes no deployment, provider-delivery, PR, or merge claim.

## Delivered boundary

The accepted implementation adds version-owned Training audiences, shared applicability, immutable Assignment
history, explicit Lesson Completion, derived current Progress, deterministic replacement-Version
Rollout preview/rules/confirm, safe local notification jobs, Admin assignment/rollout controls, and
assignment-aware Employee Home/Learning. Practice, Knowledge, Final Exam, scoring, certification,
deadlines, external delivery and deployment remain absent.

The first eight checkpoint commits are:

1. `5823a0e feat(training): add assignment and rollout persistence`
2. `a3672d0 feat(training): define version audiences and applicability`
3. `d329285 feat(training): implement assignment lifecycle`
4. `b0260b2 feat(training): expose assignment-aware employee progress`
5. `8ca8b84 feat(training): record explicit lesson completion`
6. `c7784e8 feat(training): preview version rollout impact`
7. `3b260af feat(training): confirm rollout atomically`
8. `35bdc76 feat(frontend): add assignment and completion experience`

The ninth checkpoint is `d4e0184 feat(training): complete slice 4 rollout experience`; it contains
the Admin rollout experience, browser closure and this bounded evidence.

## Mandatory scenario matrix

|   # | Accepted scenario                                                        | Executable evidence                                                                      | Result |
| --: | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ------ |
|   1 | Exact `0009` tables, constraints, indexes and empty PostgreSQL upgrade   | `tests/integration/test_assignment_persistence.py`; `tests/migration/test_migrations.py` | Pass   |
|   2 | Active same-Organization Draft audience, revision and immutability       | `tests/api/test_training_audience_api.py`                                                | Pass   |
|   3 | First Publish creates only applicable Active Assignment/jobs             | `test_first_training_publish_assigns_each_applicable_active_employee_once`               | Pass   |
|   4 | Publish replay/concurrency has no duplicate effects                      | Training publication/audience API tests                                                  | Pass   |
|   5 | Activation/reactivation applicability preserves valid facts              | activation/applicability and assignment integration tests                                | Pass   |
|   6 | Role/Location create/retain/revoke matrix is scoped and audited          | employee profile, applicability and assignment tests                                     | Pass   |
|   7 | Manual assign/revoke/reassign security, idempotency and lineage          | `tests/api/test_training_assignment_admin_api.py`                                        | Pass   |
|   8 | One current Assignment survives concurrency                              | assignment API plus database partial-unique test                                         | Pass   |
|   9 | Truthful no-Assignment Home and exact assigned next action               | employee Training API and `ActiveHomePage.test.tsx`                                      | Pass   |
|  10 | Retained assigned Version is readable; arbitrary archive is hidden       | employee Training API plus retained-review component test                                | Pass   |
|  11 | View does not write; explicit Completion is immutable/replay-safe        | employee Training API/integration plus Lesson component tests                            | Pass   |
|  12 | Exact Assignment/Lesson scope; foreign/unassigned/Paused/Disabled denial | `test_employee_completion_rejects_unassigned_foreign_paused_and_disabled_without_write`  | Pass   |
|  13 | Required-only denominator and floor Progress                             | `test_progress_uses_required_stable_lessons_and_floor_division`                          | Pass   |
|  14 | Final required Completion completes Assignment; no exam surface          | completion API/integration and OpenAPI tests                                             | Pass   |
|  15 | Replacement Publish prepares Rollout without migration                   | `test_replacement_publish_previews_rollout_without_migrating_assignment`                 | Pass   |
|  16 | Deterministic defaults and explicit changed-Lesson choice                | Rollout preview/rule API and Admin component tests                                       | Pass   |
|  17 | Stale preview rejects confirm without partial effects                    | Rollout API plus recoverable stale Admin component test                                  | Pass   |
|  18 | Confirm creates lineage/provenance and recalculates Progress             | `test_admin_confirms_previewed_rollout_with_lineage_and_carried_completions`             | Pass   |
|  19 | Confirm replay/concurrency/rollback has one atomic effect                | Rollout concurrency and forced-failure tests                                             | Pass   |
|  20 | Paused reads but cannot complete; no deadline claim                      | employee Completion API and Paused component state                                       | Pass   |
|  21 | Jobs are transactional, deduped and provider-free                        | applicability/assignment/rollout integration and rollback tests                          | Pass   |
|  22 | Exact OpenAPI without assessment/answer-key leakage                      | assignment, completion and rollout OpenAPI tests                                         | Pass   |
|  23 | Admin assignment, impact, preserve/repeat, stale and confirm UI          | `AdminFlow.test.tsx`; `AdminTrainingPage.test.tsx`                                       | Pass   |
|  24 | Employee empty/assigned/progress/completed/retained/error/Paused UI      | Home and Employee Learning component suites                                              | Pass   |
|  25 | Three-viewport Admin assignment, Employee Completion and Rollout         | `e2e/training-slice.spec.ts` in all Playwright projects                                  | Pass   |
|  26 | Full regression, coverage, migration and inventory gates                 | commands and results below                                                               | Pass   |

## Backend gate

Environment: Python 3.12.10, native PostgreSQL 16, ignored test-only environment, no SQLite.

- Ruff format: 147 files already formatted.
- Ruff lint: passed.
- strict mypy: no issues in 135 source files.
- pytest with statement and branch coverage: **363 passed, 0 failed, 0 skipped** in 626.40s.
- overall statement/branch coverage: **88%**.
- seven-file Slice 4 service boundary aggregate: **87%** across applicability,
  employee Training, audiences, Assignments, Completion, publication and Rollout services.
- important individual coverage: Rollout 91%, Completion 93%, Assignments 83%, Employee Training
  85%, publication 80%, applicability 97%.
- Alembic current head: `0009_assignment_completion_rollout (head)`.
- empty-database upgrade and `0009` downgrade/upgrade are covered by the full suite.
- Alembic autogenerate check: no new upgrade operations detected.

Exact commands are the backend commands in [`.harness/TESTING.md`](../../.harness/TESTING.md).

## Frontend and browser gate

- Prettier: passed.
- ESLint: passed.
- TypeScript project type-check: passed.
- Vitest: **14 files passed; 35 tests passed, 0 failed, 0 skipped**.
- Vite production build: passed; 50 modules transformed.
- Playwright: **12 passed, 0 failed, 0 skipped** across 1440×1000 Admin desktop, 768×1024
  Admin compact and 375×812 Employee mobile projects.
- The new focused browser boundary contributes six executions: the existing publish → Employee
  reader path now proves explicit Completion, and the new path proves Admin Assignment plus
  replacement Publish → changed-Lesson choice → refreshed preview → atomic confirm.

## Security, inventory and limitations

- Session, completed Admin MFA, Organization scope, CSRF and idempotency remain server-authoritative.
- Employee reads stay current-Assignment-scoped and retained Version access is not enumerable.
- Completion is explicit; media viewing never writes.
- Rollout stale/conflict paths retain a recoverable UI and server revalidation remains authoritative.
- No external provider call, dependency, architecture change, production data mutation, deployment,
  push, PR, merge or history rewrite occurred.
- Protected `Photos/` and local `outputs/` remain untracked, untouched, unstaged and unpublished.
- Final selective inventory and diff checks are recorded on CRA-57 after the ninth commit.

## Acceptance boundary

Denys explicitly accepted the complete nine-checkpoint implementation and authorized ordinary
fast-forward publication of `5823a0e..d4e0184`. The range is published without history rewriting.
Deployment, provider activity, PR, merge, and later product work remain separately gated.
