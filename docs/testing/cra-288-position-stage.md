# CRA-288 — position architecture checkpoint

Prerequisite baseline and isolated environment: [baseline](cra-288-baseline.md).
Boundary: stage 1 of the [commit map](cra-288-commit-map.md). This checkpoint does not complete
CRA-288: standards-backed checks, initial content and Academy remain separate stages.

## Behavior and compatibility

- Reuse organization-scoped OperationalRole for positions; authorization roles are unchanged.
- Keep one Menu module; permit multiple service, sales and venue-standards modules.
- Version module audiences independently: selected positions or all positions within the root
  training audience. Existing module versions default to all positions, preserving Waiter.
- Root training audiences retain explicit selections by default. An explicit all-positions
  choice also applies to positions created later. Draft copying preserves both audience levels.
- Enforce module visibility for discovery, direct lesson and asset reads, completion,
  interactive attempts and history. Optional modules do not increase required progress.
- A position change that changes available modules revokes the previous assignment and creates
  a linked replacement. Existing timestamps/results remain; unchanged legacy assignments retain
  their behavior. Rollout progress and preserved completions use applicable modules. Position
  changes invalidate a prior rollout preview; older preview fingerprints require recomputation.
- Publication checks every module and prevents empty required modules. The existing single-Menu
  readiness response remains compatible.
- Existing editor gains module selection, module creation and position audience controls.
  No administration redesign, dependencies or separate content-management subsystem.

Migration `0022_module_position_audiences` adds the module audience relation, audience flags and
domain constraints. Existing assessment history survives upgrade. Downgrade refuses to discard
new non-Menu or position-scoped content. Applied only to the dedicated local test database.

## TDD evidence

The initial module-creation API returned 404. The position visibility/direct-access matrix
failed nine cases before enforcement. History, stored attempts and draft cloning failed three
additional cases before their guards/copying were extended.

Additional RED cases demonstrated ignored non-Menu publication errors, rejection of the root
all-positions flag, stale completed assignments after a position change, rollout counts including
other positions, confirmation of a stale position preview, and unblocked empty required modules.
Frontend RED cases lacked the all-positions control, module selection and creation form.

Setup corrections are not behavioral RED evidence: a duplicate pytest test-module basename,
an incorrect test join, a shell-quoted selection expression and SQL result materialization were
corrected before the associated behavioral assertions passed.

## Verification

All passing groups below had zero failures and zero skipped tests; groups overlap and must not
be added together as a unique-test total.

- Affected training/audience/applicability/publication/rollout group: **77 passed**.
- Final position, publication, rollout, employee training and interactive attempt/answer/history
  regression group: **96 passed**, 186.95 seconds.
- Final module API matrix, including actual foreign-tenant roles and exact one/multiple/all
  replacement: **19 passed**, 41.32 seconds.
- Migration and training-model group: **23 passed**, including old Waiter history preservation
  and refusal of a lossy downgrade.
- Full frontend Vitest: **169 passed**, 32 files.
- Playwright full run initially had **84 passed / 3 failed**: an old partial-name locator matched
  both audience-save buttons. After scoping/exact matching, all six affected training scenarios
  passed across desktop, compact and mobile. The final six-scenario run also checks the new
  forms and horizontal overflow. This is not reported as a new full 87-test pass.
- A backend run initially had **66 passed / 1 failed** because the new required-module check
  duplicated the legacy single-Menu readiness error. Compatibility was restored and the final
  96-test group above passed.
- Ruff check/format, strict mypy (**263 source files**), frontend TypeScript, ESLint, Prettier
  and build: passed. Build retains the existing chunk-size warning (approximately 547 KB JS).
- Alembic current/check: head `0022_module_position_audiences`, no pending model/schema drift.
- Mobile screenshot of the new-module form inspected: readable labels and controls, no clipping
  or horizontal overflow. Browser checks use mock APIs; they do not certify a remote environment.

Representative backend commands (APP_ENV/test connection supplied only to the process):

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_position_training_api.py tests/integration/test_position_training.py tests/api/test_training_rollout_api.py tests/api/test_training_publication_api.py tests/api/test_employee_training_api.py tests/integration/test_interactive_attempt_service.py tests/integration/test_interactive_answer_service.py tests/integration/test_interactive_history_service.py tests/api/test_interactive_cycles_api.py -q -p no:cacheprovider --tb=short
rtk ..\.venv\Scripts\python.exe -m pytest tests/migration/test_migrations.py tests/integration/test_training_models.py -q -p no:cacheprovider --tb=short
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_position_training_api.py -q -p no:cacheprovider --tb=short
rtk ..\.venv\Scripts\python.exe -m mypy --strict app tests
rtk ..\.venv\Scripts\python.exe -m alembic current --check-heads
rtk ..\.venv\Scripts\python.exe -m alembic check
```

Frontend commands used the existing installation with `--config.verify-deps-before-run=false`;
no install or lockfile update. Commands: Vitest run, typecheck, lint, format:check, build,
Playwright full run, then `playwright test e2e/training-slice.spec.ts` after the locator fix.

## Review and remaining gates

Reviewed the tenant-scoped foreign keys and mutation queries, CSRF/Admin/MFA dependencies,
revision locking, immutable-version rejection, direct/stored-attempt access, copied audiences,
history retention and downgrade guard. New data and API fields are additive. No answer payload,
MFA rule, Final Exam threshold or retake rule changes are included in this checkpoint.

The full backend/coverage and full browser suites must run again after all CRA-288 stages.
No push, merge, production/staging action, secret file or unrelated main-worktree edit.
