# Two-person demo candidate verification — 2026-09-10

## Completed local commit execution — 2026-09-10

Denys explicitly authorized the mapped local commits. All six implementation maps below
have been committed in order, with shared navigation consolidated into checkpoint 16.
Historical empty-index/uncommitted/no-authorization wording in the original audit and feature
reports describes their preparation dates and is superseded by this execution record.
Local commits do not authorize push, Linear updates, deployment or non-test data operations.

Each implementation checkpoint was checked in an exported staged-tree snapshot with existing
dependencies and, where relevant, the dedicated test database. Final successful test runs have
zero failures, errors or skips. Suites overlap; counts must not be added as unique tests.

| Checkpoint | Commit | Outcome | Verification |
| --- | --- | --- | --- |
| 1 | `4dce657` | feat(frontend): add public Bacara editorial entry | 10 focused frontend tests; format, lint, types, build PASS |
| 2 | `5217293` | test(frontend): verify responsive public entry | 76 Vitest and 51 Playwright PASS |
| 3 | `0a7f5ea` | feat(frontend): add read-only Employee profile | 83 Vitest; format, lint, types, build PASS |
| 4 | `90e609c` | test(frontend): verify Employee profile browser journey | 60 Playwright PASS |
| 5 | `ca6d457` | feat(backend): admit verified reference questions to Practice | 101 backend tests; Ruff format/check and mypy PASS |
| 6 | `c513450` | docs: record reference-question Practice evidence | Documentation links and diff PASS |
| 7 | `0ee6a0b` | feat(auth): revoke other sessions while preserving current login | 33 backend tests; Ruff format/check and mypy PASS |
| 8 | `abe86a2` | feat(frontend): add logout of other devices | 85 Vitest, 63 Playwright; format, lint, types, build PASS |
| 9 | `ddb053f` | docs: record other-device logout evidence | Documentation links and diff PASS |
| 10 | `9c93def` | feat(backend): add scoped organization Dashboard aggregates | 24 backend tests; Ruff format/check and mypy PASS |
| 11 | `734a1e3` | feat(frontend): make Admin Dashboard the management landing page | 89 Vitest, 69 Playwright; format, lint, types, build PASS |
| 12 | `a34427f` | docs: record Admin Dashboard semantics and evidence | Documentation links and diff PASS |
| 13 | `f141685` | fix(auth): revoke outstanding reset links on password change | 23 backend tests; Ruff format/check and mypy PASS |
| 14 | `6236d25` | fix(security): bound public rate-limit state and retire expired budgets | 124 backend tests; Ruff format/check and mypy PASS |
| 15 | `6e34d58` | docs: record CRA-170 security correction evidence | Documentation links and diff PASS |
| 16 | This documentation checkpoint | Completion report and selective STATUS/CONTEXT/testing navigation | Staged links, exact diff and inventory review |

The 354 recorded source/test/build-input hashes still match the candidate that passed the full
865-test PostgreSQL run below. Application/test content is preserved, with no additional code
changes during commit execution. Backend static checks on the final code snapshot pass for
254 formatted files and 232 mypy source files. The final frontend snapshot passed 89 Vitest
and 69 Playwright cases, format/lint/types and production build.

Execution adjustments affected only local verification helpers under excluded `outputs/`:
an empty stale Git lock was moved aside after checking no Git process was active; staged exports
use canonical LF bytes to avoid Windows checkout conversion; frontend checks invoke the existing
installed package entrypoints instead of pnpm dependency-location reconciliation. An output
encoding exception after checkpoint 3's successful build was verified against its complete log;
the helper output encoding was corrected. No dependencies or production files were rewritten.

The final documentation checkpoint adds this report and only new completion sections in
`STATUS.md`, `CONTEXT.md` and `docs/testing/README.md`, staged over their committed baselines.
All earlier unrelated dirty documentation, source/build drafts, original `Photos/` and runtime
outputs are preserved outside these commits. The selected staging source remains `fafec73`;
this local series is not automatically published or selected for deployment.

## Original audit scope and authority (before commit authorization)

Denys requested the ordered audit follow-up to proceed. This checkpoint records local candidate
review and verification under CRA-122. It does not accept the feature issues on the owner's behalf
or authorize commits, push, source binding, migration, deployment, provider sends or non-test data.
No product implementation is added by this documentation checkpoint.

Base: `main@fafec73ad7f3438e1b545acea7cde3018b7f2fbf`. Local `origin/main` matches; a fresh remote
publication preflight is still required. The working tree contains six bounded implementation
candidates plus earlier documentation/preparation changes. The Git index is empty.

Documentation-only TDD exception: verify source references, exact path inventory, evidence,
relative links and diff hygiene. Application suites below validate the existing candidate.

## Candidate and selective publication boundaries

Preserve the individual ordered maps rather than making one whole-worktree commit:

1. CRA-131 public entry: [two checkpoints and asset provenance](public-start-editorial.md).
   Public page/CSS, four approved photo copies and official SVG; App public-route/test hunks,
   LoginPage branding and index metadata; then its browser test and evidence/navigation.
2. CRA-147 Employee profile: [two checkpoints](employee-profile.md). New profile page/test/CSS,
   App profile-route hunk, EmployeeShell and its test; then profile browser test/evidence.
3. CRA-149 Practice: [two checkpoints](practice-reference-families.md). Only family admission,
   the new reference-family integration test and deterministic existing generation assertion;
   then its evidence/current-state documentation hunks.
4. CRA-150 other-device logout: [three checkpoints](logout-other-devices.md). Backend sessions,
   auth route and API test; shared LogoutButton/component/browser tests; then evidence/navigation.
5. CRA-151 Admin Dashboard: [three checkpoints](admin-dashboard.md). New backend
   service/schema/route/test and router registration; frontend Dashboard page/test/CSS/contracts,
   App/AdminShell/SessionGate routing and corresponding tests; then evidence/navigation.
6. CRA-170 security corrections: [three checkpoints](security-fixes-cra-170.md). First reset-token
   revocation and recovery tests; then bounded rate-limit allocation/reclamation and tests;
   then its evidence and STATUS hunk.

Shared-file staging must preserve these boundaries. In particular, App.tsx spans CRA-131/147/151;
App.test.tsx combines public entry with the final Dashboard destination. The CRA-131 checkpoint
must use the then-existing Admin destination and CRA-151 must introduce its later expectation.
The exact logout-selector edits in vertical-slice.spec.ts belong with the new logout control;
the post-MFA Dashboard expectation belongs with CRA-151. Password recovery has separate CRA-170
token-invalidation and rate-storage hunks. Do not stage whole shared files prematurely.

Each intermediate checkpoint must build and pass its mapped checks. Index-only staging does not
prove that an intermediate commit is GREEN; validate the staged tree before committing. Preserve
the final working copy and accepted history. No squash/amend/reset/rebase is part of this plan.

Earlier CRA-122 documentation/source/build drafts are a separate preparation boundary. Inventory
their exact diff before any later publication. This report is one new documentation checkpoint.

Excluded: original `Photos/`, all `outputs/` (including customer content), `.env*`, credentials,
local helpers, caches, coverage/browser output and the metadata-only question_generation.py mark.
CRA-131's copied frontend assets are distinct from the protected originals; publication still
needs owner visual/asset acceptance. Existing fallback font and photo overlays remain explicit.

## Pre-commit verification ledger

| Check | Result |
| --- | --- |
| Vitest, `rtk pnpm test --maxWorkers=2` | 89 passed, 0 failed/skipped, 24 files; earlier September 10 audit in this session |
| Backend Ruff check/format | Passed; 254 files already formatted, September 10 audit |
| Backend strict mypy | Passed; 232 source files, September 10 audit |
| Source Alembic heads | `0019_auth_security_budgets`; does not query staging |
| Frontend production build | Passed; TypeScript plus Vite |
| Frontend Prettier and ESLint | Passed |
| Playwright, one worker | 69 passed, 0 failed/skipped, three viewports; 2.1 minutes |
| Frontend delivery artifact tests | 2 passed, 0 failed/skipped |
| Railway topology TypeScript check and static tests | Check passed; 3 tests passed, 0 failed/skipped; no provider operation |
| Existing offline import integrity | 4 checks passed: current schema validates the artifact; schema/artifact hashes match saved report; inventory source hash matches report |
| Docker engine availability | `docker version` failed: desktop-linux engine pipe absent; client 29.7.2 is installed. Image builds/container smoke not run |
| Initial full PostgreSQL run | 849 passed, 0 failed, 16 setup errors; 2238.33 seconds. Windows temp-folder access denied; coverage saving also failed. Not a full PASS |
| Isolated environment diagnosis | Default temp reproduces WinError 5; new temp under restricted token also fails. Permitted unrestricted retry: 16 passed, 0 failed/errors/skipped; coverage save succeeded |
| Fresh full dedicated PostgreSQL retry | 865 passed, 0 failed/errors/skipped in 2093.38 seconds; new temp and coverage paths, permitted unrestricted Windows token |
| Independent statement coverage | 11657/12406 = 93.96% PASS |
| Independent branch coverage | 2084/2590 = 80.46% PASS |
| Fixed nine-file critical aggregate | 1325/1476 = 89.77% PASS; complete application source inventory validated |
| Test-database upgrade/current-head/no-drift | Passed; `0019_auth_security_budgets`; no new upgrade operations detected |
| Candidate source stability | All 354 recorded source/test/build-input hashes unchanged through completion |
| Documentation relative links | 7 checked, 0 broken |
| Final inventory/diff hygiene | Passed; Git index empty; scope recorded below |

Full backend command uses the guarded test-environment loader in `.harness/TESTING.md`,
`APP_ENV=test` and a dedicated `horeca_test` database. The initial separate coverage file under
`.pytest_cache` could not be saved. The retry uses fresh `outputs/verification-cra122-*` runtime
storage, an absolute `COVERAGE_FILE` ending in `full.coverage`, and a new `--basetemp` ending in
`full-tmp`. Both remain excluded from publication; existing temporary folders are preserved.
No environment values are recorded here. Command, with the run's new temp path substituted:
`rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --basetemp=<new-run-temp> --cov=app --cov-branch --cov-report=term-missing`.
The fresh successful run alone produced `full.json`; all three gates pass without old/preflight
coverage being merged. No code, dependency or test configuration was changed to work around the
Windows execution boundary.

Browser APIs are mocked. These checks do not prove live authentication, email, storage, hosted
content readiness, migration, cron behavior, resource consumption or customer acceptance.
The passing `test_synthetic_invitation_to_passing_final_result_chain` exercises invitation and
activation through the API, but seeds completed training, qualifying Practice and exam state
with factories before saving/grading answers through services. It is not a full user-driven
import-to-certification acceptance flow; the real-origin pipeline must still be executed.

## Read-only review observations

The reviewed backend diff preserves authenticated-user/session derivation for logout, CSRF and
Origin dependencies, scoped Dashboard predicates, exact source/version filters for Practice,
atomic reset-link invalidation and bounded PostgreSQL rate-state admission. No new dependency,
migration, provider or API privilege is introduced. Dashboard and profile requests have stale
request cleanup and explicit failure/retry states. This is a focused review, not a new broad
security scan or proof of every possible defect.

The full MASTER SPEC reread confirms historical wording that must not drive this rollout:
automatic staging deployment on `main`, the old 95% critical-branch target, and earlier
implementation-next-step instructions are superseded by START HERE, current CRA-13 gates and
CRA-122 delivery decisions. The two-person demo does not waive the later pilot/production gates.
Human approval of generated questions, explicit Employee activation and separate technical
operator/Admin identities remain material to the current demonstration.

## Next implementation prerequisite: account provisioning

The [canonical staging plan](https://linear.app/craftspacee/document/cra-122-stage-2-staging-source-variables-and-rollback-plan-dde7a78ff215)
and local preparation specify a first-operator
transaction but no tested executable exists. Existing `app.operations.bootstrap_venue` requires
an active operator and grants that same User organization-admin access. The two demo personas
must remain separate from the technical operator.

Prepare a separate bounded implementation issue with these coherent checkpoints:

1. A guarded, dry-run-first initial-operator operation using existing Settings, email normalization,
   PasswordManager, User/AdminAccess/Audit models and transaction locking. Password entry is hidden,
   never an argument/file/log. Test target/revision guards, collisions, rollback and replay.
2. An explicit organization-admin grant operation for an existing separate User and exact active
   Organization, authorized by the operator. Preserve password, Employee access and history; never
   add platform scope or bypass normal MFA. Test foreign scope, partial state, rollback and replay.
3. Exact operator/venue/Admin/Employee preparation runbook, focused PostgreSQL verification and
   a fresh protected-boundary review. Non-test execution remains separately approved.

Resolve the separate Admin User creation path in that issue before implementation; the Employee
invitation endpoint cannot be described as granting Admin privileges. No endpoint or schema is
invented by this proposal. CRA-122 itself does not authorize production-code edits.

## Staging sequence after candidate acceptance

September 10 read-only refresh: the public `/healthz` returns the Railway 404 fallback.
The source-binding support thread still has two replies and no verified no-initial-deploy
procedure. An explicit-project/environment `railway status --json` read confirms all nine
application services have null repository/image and latest deployment, with zero active
deployments; the five cron schedules are null. PostgreSQL has one active deployment and its
latest status is SUCCESS (`46bb859f-58c8-4318-aa5a-1aacbf62d522`).
The CLI does not expose a usable pending-change count in this response; the earlier 44-change
inventory, resolved variables, grants, storage and resource controls have not been revalidated.
The initial sandbox network attempt failed; the permitted read-only retry succeeded. No provider
configuration or application-data mutation occurred.

The official [Railway up documentation](https://docs.railway.com/cli/up) and installed CLI help
confirm that `up` uploads **and deploys**; `--detach` only stops waiting. There is no documented
upload-only switch in that command. A reviewed export of an accepted immutable commit could be
the alternative delivery source, with an explicit project, environment and service per invocation.
This remains a proposal requiring approval before execution; never upload the dirty workspace,
use `--no-gitignore`, or treat upload as a harmless source-preparation action.

Refresh the existing nine-service inventory; resolve supported immutable delivery and exact pending
settings/cost controls. Do not recreate prepared DB roles or application keys. After the concrete
operation approvals: migration once, runtime grants, API, worker, public web; keep cron schedules
disabled until their separately verified checks. Provision operator and two demo identities through
the reviewed flows. Prove Admin MFA, invitation, Pending, explicit Activation, assigned learning,
saved results and session revocation on the real origin. Then complete Practice/Final/Results and
the remaining CRA-122 acceptance ledger. Synthetic smoke and Bacara content import are distinct.

CRA-148 already has a local MenuImportCreate file and a saved 2162-pass offline validation report;
do not regenerate it as missing work. September 10 read-only verification confirms schema and
artifact hash matches, inventory/report source-hash agreement, and validation by the current
MenuImportCreate schema. This is four fresh integrity checks, not a rerun of all 2162 historical
assertions or a fresh retrieval of the external customer source. The separately approved Admin
import/review/publish path is still required. Offline question counts are not server readiness.

## Checkpoint handoff

The authorized local commit execution is recorded at the top of this report. Its final
documentation checkpoint contains this report and only the new completion navigation in
`STATUS.md`, `CONTEXT.md` and `docs/testing/README.md`. Earlier unrelated documentation and
preparation changes remain in the working tree. Generated verification files under `outputs/`
are local runtime evidence, excluded from every commit map.

Local commits do not constitute owner feature acceptance or a published staging candidate.
No push, Linear write, provider mutation or deployment was performed. Account provisioning and
the supported delivery choice remain the next bounded work before real-origin acceptance.
