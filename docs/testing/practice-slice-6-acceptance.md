# MVP Vertical Slice 6 — Practice local acceptance evidence

**Bounded issue:** [CRA-64](https://linear.app/craftspacee/issue/CRA-64)  
**Canonical plan:** [CRA-63](https://linear.app/craftspacee/issue/CRA-63)  
**Evidence date:** 2026-08-31  
**Status:** accepted by Denys; CRA-65 synchronization is Done and published through `4164b9c`

This record maps the mandatory 40-scenario CRA-63 gate to evidence that actually ran. Linear
remains canonical for product, API, data, RBAC and acceptance contracts. CRA-65 records the exact
remote publication evidence; no PR, merge, deployment, provider activity or production mutation
is included.

## Delivered boundary

The eight local checkpoints implement Training-scoped `whole_menu_knowledge_check` persistence,
source-safe item-level Practice pooling/readiness, one immutable ten-Question Attempt over ten
distinct Menu Items, feedback-free progressive Answer saves, explicit atomic finish, Knowledge
bands, critical-allergen evidence, durable earned Final Exam eligibility, Latest/Best/history,
Admin readiness and responsive Employee Practice.

Practice creates only the target `menu_final_exam` Assessment root needed by the eligibility FK.
It creates no Final Exam Version, pool, Attempt, Result or execution route. Certification,
management Results, Attention/Retakes, providers, deployment and real Bacara content remain out of
scope.

## Mandatory scenario matrix

|   # | Accepted scenario                                                                           | Executable evidence                                      | Result |
| --: | ------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------ |
|   1 | Missing-component generation is verified, deterministic and idempotent                      | question-generation unit/integration suites              | Pass   |
|   2 | Unsupported, ambiguous, unverified, price/description-only facts are excluded               | generation unit/integration suites                       | Pass   |
|   3 | Selection returns ten Questions over ten stable Menu Items                                  | selection unit and Practice integration suites           | Pass   |
|   4 | Selection spreads/rotates when the pool permits                                             | selection unit suite                                     | Pass   |
|   5 | Nine Items block; ten start; stale/foreign rows do not count                                | readiness/selection and tenant tests                     | Pass   |
|   6 | Exact Knowledge boundaries and >=4/10 qualification use integer arithmetic                  | grading unit and finish integration suites               | Pass   |
|   7 | Latest, Best and durable eligibility remain independent                                     | finish/history integration suite                         | Pass   |
|   8 | Empty database, round-trip, current head and no-drift reach `0014_practice_persistence`     | migration suite and Alembic gates                        | Pass   |
|   9 | Type/count/feedback/threshold constraints reject invalid configurations                     | persistence contract/integration suite                   | Pass   |
|  10 | Cross-tenant/version pool, Attempt and eligibility relations fail closed                    | persistence and Practice integration suites              | Pass   |
|  11 | One active Attempt and one active earned eligibility survive concurrency                    | persistence and finish concurrency suites                | Pass   |
|  12 | Eligibility reset-state constraints exist without exposing a reset API                      | persistence contract/integration suite                   | Pass   |
|  13 | Existing five-question Interactive rows and behavior remain valid                           | full Interactive regression                              | Pass   |
|  14 | Summary covers no Assignment/incomplete/preparing/ready/paused                              | Practice service/API suite                               | Pass   |
|  15 | Start blocks incomplete, unready, foreign, revoked and paused scope                         | Practice integration/API suite                           | Pass   |
|  16 | Start snapshots ten distinct current Items and replays the active Attempt                   | Practice integration/concurrency suite                   | Pass   |
|  17 | Active Attempt reads expose no grading key, correctness or explanation                      | response-schema/API non-exposure tests                   | Pass   |
|  18 | Answer validates snapshot IDs, owner/current scope and lease generation                     | Answer integration/API suite                             | Pass   |
|  19 | Answer replay is stable; conflicts and overwrites fail                                      | Answer idempotency/concurrency suite                     | Pass   |
|  20 | Every Answer response, including the tenth, remains feedback-free                           | Answer service/API and Employee tests                    | Pass   |
|  21 | Takeover preserves snapshots/Answers and invalidates the old lease                          | Practice service and Employee tests                      | Pass   |
|  22 | Pause freezes effective expiry; expiry remains immutable history                            | Practice lifecycle integration suite                     | Pass   |
|  23 | Incomplete finish creates no Result or eligibility                                          | finish integration suite                                 | Pass   |
|  24 | Finish grades once and exposes review only after completion                                 | finish concurrency/API/UI suites                         | Pass   |
|  25 | Current qualifying 4/10 earns exactly one eligibility                                       | finish/persistence integration suites                    | Pass   |
|  26 | Missing current prerequisites prevent eligibility                                           | finish integration suite                                 | Pass   |
|  27 | A later 3/10 updates Latest without removing Best/eligibility                               | history integration suite                                | Pass   |
|  28 | Critical allergen flags persist without Slice 8 rows                                        | finish/persistence integration suite                     | Pass   |
|  29 | Rollout/reassignment prevents stale eligibility earning                                     | Practice lifecycle/finish integration suite              | Pass   |
|  30 | Own cursor history is stable and foreign identifiers do not enumerate                       | Practice history/API suite                               | Pass   |
|  31 | OpenAPI contains approved routes and omits grading/provenance secrets                       | API/OpenAPI tests                                        | Pass   |
|  32 | Existing Interactive service/API behavior stays green                                       | full backend and frontend regression                     | Pass   |
|  33 | Practice route is usable at mobile, compact and desktop widths                              | `e2e/practice-slice.spec.ts`                             | Pass   |
|  34 | Availability/pause/expiry/device states expose truthful actions                             | Employee component suite                                 | Pass   |
|  35 | Ten-Question UI saves server-confirmed Answers and preserves retry state                    | Employee component/browser suites                        | Pass   |
|  36 | No correctness or explanation renders before finish                                         | Employee component/browser suites                        | Pass   |
|  37 | Finish renders score, band, qualification and completed review                              | Employee component/browser suites                        | Pass   |
|  38 | Latest/Best/history are distinct with no peer/leaderboard data                              | Employee component/browser suites                        | Pass   |
|  39 | Home `open_practice` and bottom navigation reach Practice                                   | Home/Shell component and legacy browser suites           | Pass   |
|  40 | Protected ten-Answer finish earns eligibility; weaker-history semantics remain server-owned | Practice browser path plus backend finish/history suites | Pass   |

## Backend gate

Environment: Python 3.12.10, native PostgreSQL 16, ignored test-only environment, no SQLite.

- Ruff format and lint: passed.
- strict mypy: passed for 162 source files.
- full pytest with statement/branch coverage: **436 passed, 0 failed, 0 skipped; 88% total**.
- predeclared five-file critical Slice 6 aggregate across question generation, question review,
  Practice Attempt, Answer and Result services: **85% statement/branch aggregate**.
- migration head: `0014_practice_persistence`; migration round-trip, current-head and metadata
  no-drift checks: **passed; no new upgrade operations detected**.
- acceptance uncovered one calendar-brittle pre-existing Invitation fixture. RED was 12 failures
  because a 2026-08-30 expiry had become earlier than PostgreSQL `created_at` on 2026-08-31.
  Moving only the fixed test clock to 2030 produced 12 passed; no production behavior changed.

## Frontend and browser gate

- Prettier, ESLint and TypeScript project checking: passed.
- Vitest: **17 files passed; 53 tests passed, 0 failed, 0 skipped**.
- Vite production build: passed; 53 modules transformed.
- Playwright: **18 passed, 0 failed, 0 skipped** across 1440×1000, 768×1024 and 375×812.
- The new browser case runs the complete feedback-free ten-Answer flow, verifies protected
  mutations, explicit finish, 6/10 qualification, critical-allergen review, Latest/Best and no
  Passed/Failed state across 1440×1000, 768×1024 and 375×812.
- Focused RED/GREEN evidence also proves the distinct `no_assignment` and `training_incomplete`
  availability states, the single Learning action for incomplete training, and the accepted
  `very_weak` display label `Не пройдено`.
- Route mocks cover the browser contract/UI boundary; PostgreSQL persistence, races, rollback and
  eligibility are covered by the backend integration gate.

## Security, inventory and limitations

- Employee scope is derived from the authenticated Session; callers cannot select a tenant,
  Employee, Assignment or grading source.
- Mutations require the existing CSRF and idempotency protections. Takeover and Answer/finish use
  the server lease generation.
- Active Attempt and Answer responses expose no correctness, correct Option IDs, explanation,
  grading payload, source fingerprint or provenance. Completed review still omits hidden grading
  payload and provenance.
- Automatic Practice admission is limited to verified components, allergens and deterministic
  missing-component facts. Category/description remain Interactive-only; assembly/serving stays
  excluded because no approved structured source proves it.
- Critical allergen evidence is immutable, but Attention/Retake persistence and behavior remain
  Slice 8 scope.
- `Photos/`, `outputs/`, `.env*`, caches, local test output and secrets remain untracked/ignored as
  applicable, untouched by the implementation map and unstaged.
- No dependency, architecture expansion, provider/resource call, non-test data mutation,
  deployment, push, PR, merge or history rewrite occurred.

## Local checkpoint boundary

The accepted local range starts after published baseline `c79db9d` and contains exactly eight
selective checkpoints. Checkpoints 1–7 end at `619c26e`; checkpoint 8 ends at `cc1c05a` and records
the final evidence and synchronized repository/Linear state. CRA-65 is Done; its documentation
checkpoint and exact ordinary-publication evidence are published through `4164b9c`.
