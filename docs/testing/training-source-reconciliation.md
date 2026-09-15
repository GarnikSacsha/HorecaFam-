# Training source reconciliation — 2026-09-15

## Outcome and authority

Denys authorized continuing the September 15 audit plan. The main checkout now contains the
CRA-172 Menu dependency recovery already deployed with the CRA-202 audience editor. This is
local source reconciliation under the existing bounded recovery issue, followed by CRA-122 local
documentation hygiene. No new product behavior beyond those existing contracts is introduced.

The six source/test files were copied from the reviewed, sealed September 15 delivery packet
after checking their manifest hashes. The retained audience GET/panel and the recovery UI coexist.
Worktree 54bf and the sealed packet were not edited. This resolves the missing source in the
main checkout. Denys subsequently explicitly authorized the three selective local commits below.
The series builds on `d88cb61`; [STATUS](../../STATUS.md) records its source checkpoints.

## Exact selective boundaries

1. `fix(training): reconcile deployed menu dependency recovery`
   - `backend/app/api/routes/training.py`
   - `backend/app/schemas/training.py`
   - `backend/app/services/training_drafts.py`
   - `backend/tests/api/test_training_menu_dependency_api.py`
2. `fix(admin): preserve menu recovery beside audience editor`
   - `frontend/src/admin/AdminTrainingPage.tsx`
   - `frontend/src/admin/AdminTrainingPage.test.tsx`
   - `docs/testing/training-source-reconciliation.md`
3. `docs: reconcile current delivery and separate harness history`
   - `.harness/GIT-WORKFLOW.md`, `.harness/TESTING.md`, `.harness/START-HERE.md`
   - `STATUS.md`, `CONTEXT.md`, `README.md`, `docs/testing/README.md`
   - `docs/history/harness-checkpoints-through-2026-09-15.md`

Denys explicitly authorized this three-commit map on September 15 after reviewing the results.
Documentation files were already dirty: stage only reviewed reconciliation hunks, not every prior edit in these paths.
Local preparation scripts, backups and outputs are excluded from the commit map.

## RED and GREEN evidence

Tests were transferred before production code.

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend RED: draft created before Menu publication | 0 | 1 | 0 |
| UI RED: explicit recovery action | 0 | 1 | 10 filtered out |
| Final PostgreSQL recovery/audience/publication/Admin/draft-service suite | 51 | 0 | 0 |
| Final Admin Training page and audience panel suite | 17 | 0 | 0 |
| Browser Training publication/reference scenario, three viewports | 3 | 0 | 0 |

Backend RED reached the existing Draft creation and Menu publication path, then received 404
instead of 200 from the missing recovery endpoint. UI RED failed because the recovery button
was absent. Neither failure was attributed to setup. Existing test expectations were preserved.

Backend GREEN command, from `backend/` after the harness's guarded dedicated-test environment load:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_training_menu_dependency_api.py tests/api/test_training_audience_api.py tests/api/test_training_publication_api.py tests/api/test_training_admin_api.py tests/integration/test_training_draft_service.py -q -p no:cacheprovider --tb=line --show-capture=no
```

Result: 51 passed in 166.39 seconds. Ruff check, Ruff format check and strict mypy passed for
the four mapped backend files. Tests used the existing dedicated PostgreSQL database;
no migration command or non-test database operation was performed by the agent.

Frontend checks, from `frontend/`:

```powershell
rtk pnpm test --maxWorkers=2 src/admin/AdminTrainingPage.test.tsx src/admin/AdminTrainingAudiencePanel.test.tsx
rtk pnpm build
rtk pnpm exec eslint src/admin/AdminTrainingPage.tsx src/admin/AdminTrainingPage.test.tsx
rtk pnpm exec prettier --check src/admin/AdminTrainingPage.tsx src/admin/AdminTrainingPage.test.tsx
rtk pnpm test:e2e --grep "admin publishes Training"
```

All passed. Build includes TypeScript compilation. Existing dependencies were used without
installation. Browser tests use mock API responses; they are not authenticated staging acceptance.
The existing Windows sandbox spawn restriction required approved execution outside the sandbox
for frontend tools, consistent with the preceding audit. No assertions or timeouts were weakened.

## Separated boundary review

After inspecting the merged diff, a separate review pass traced the actual route dependencies,
Organization Admin/MFA guard, CSRF/Origin check, tenant/location predicates, Draft revision lock,
the unique Published Menu invariant and the Menu publication row-lock interaction. Recovery
persists dependency, revision and safe audit atomically and rolls back on failure. The UI keeps
explicit mutation, busy-state exclusion, missing-menu/revision errors and subsequent refresh.
The existing audience GET and panel were preserved unchanged outside the reviewed integration.

No new high/critical issue was identified in this bounded reconciliation. This is not a full
security scan. Full backend coverage, full Playwright regression, provider delivery and live
content editing were not rerun. The earlier audit's intermittent Admin Menu 308-item test timeout
remains a separately recorded concern; this reconciliation did not change those files/tests.

## Documentation hygiene

The Git workflow now contains operating rules instead of a dated deployment ledger. The testing
harness retains supported environments, exact commands and independent 80% statement/branch/
critical-aggregate gates. Both complete former harness texts are preserved in the
[historical archive](../history/harness-checkpoints-through-2026-09-15.md), with rebased links.
No security, approval, TDD or test-DB guard was weakened.

The leading [STATUS checkpoint](../../STATUS.md) owns current Git/runtime/acceptance facts.
README, CONTEXT and the testing index route there; their earlier content is preserved inside
explicitly historical sections. Historical anchors remain available. Global harness, upstream
pin and external Linear documents were not modified. The global upstream was already verified
unchanged during the preceding audit; this step does not install a new global instruction set.

Final documentation checks: 194 relative file links resolved, zero broken. Eight preservation
assertions passed: both full old harness texts are archived, all four navigation histories are
retained, Git operating rules are identical, and the test-environment/command block is identical.
All six transferred files match their sealed manifest hashes exactly. `git diff --check` passed;
the final Git index is empty. Only the six mapped source/test paths, nine mapped documentation
paths and local excluded preparation/evidence outputs were changed by this follow-up.

## Next boundary

Complete the authorized selective commit series, then prepare worker sender/source and
invitation/job verification. DNS is connected according to Denys; real delivery and Employee
acceptance remain open. A future worker deployment/send needs its concrete approved operation.
No push, deployment, provider call, email, live audience update, content publication or Linear
write was performed in this reconciliation.

## Authorized pre-commit verification

The mapped checks were rerun before the authorized commit series: 51 PostgreSQL tests, 17 UI
tests and three Playwright scenarios passed, zero failed/skipped in their final runs. Scoped
Ruff format/check, mypy, ESLint, Prettier and the TypeScript/Vite build passed again. Six source
files remain identical to the reviewed deployed overlay. For the documentation checkpoint,
the four navigation files stage the new current sections and historical wrapper over their
previous committed history; older unrelated working-directory history edits remain unstaged.
The new full harness archive is deliberately included in the approved preservation boundary.
