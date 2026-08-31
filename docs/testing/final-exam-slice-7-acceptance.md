# MVP Vertical Slice 7 — Final Exam local acceptance evidence

**Bounded issue:** [CRA-67](https://linear.app/craftspacee/issue/CRA-67)

**Planning source:** [CRA-66](https://linear.app/craftspacee/issue/CRA-66)

**Evidence date:** 2026-08-31

**Status:** verified local acceptance candidate; awaiting Denys's acceptance and separate
publication authorization

This record describes only evidence that actually ran for the authorized CRA-67 checkpoint map.
The canonical product, API, data, RBAC and acceptance contracts remain in Linear.

## Delivered boundary

- Builds readiness from at least 20 eligible source-safe questions, targeting rotation across a
  larger pool and balancing component, allergen and missing-component facts.
- Requires durable Practice eligibility and a completed current Assignment before a Final Exam can
  start.
- Snapshots exactly 20 questions into one immutable active Attempt with seven effective inactivity
  days, pause-aware expiry and explicit device takeover.
- Saves all answers idempotently without correctness, explanation or feedback before final finish.
- Requires an explicit final confirmation, grades atomically once and treats 14/20 as passed and
  13/20 as failed.
- Exposes completed review, critical-error evidence, Latest/Best/history and certification. A
  failed attempt can be retaken immediately; a passed certification exposes no retake action.
- Adds Organization-scoped Admin Results overview/detail and Final Exam readiness without a
  leaderboard or separate certification table.
- Adds responsive Employee start/resume/execution/result/history and Admin Results/readiness UI.

## RED → GREEN evidence

- Readiness/pool, eligibility/lifecycle, feedback-free answers, finish/certification, canonical
  Admin Results, Admin UI and Employee UI were each introduced through focused failing tests and
  closed before their checkpoint commit.
- The new browser journey initially failed in all three viewport projects because an assertion for
  `Пройдено` also matched history. Scoping it to the result boundary produced 3/3 green without
  weakening the business assertion.
- The first focused PostgreSQL acceptance run failed inside the evidence test after a rollback had
  expired ORM objects. Capturing immutable IDs before rollback fixed the test harness; production
  code did not change. The rerun passed and retained the concurrent finish proof.
- The prior full backend regression exposed one old generation fixture that did not isolate the new
  readiness call. Adding the missing monkeypatch produced a focused pass and the complete rerun
  finished green.

## Backend gate

- Python 3.12.10 and native PostgreSQL 16 with `APP_ENV=test` and the ignored dedicated test
  database.
- Ruff format check: passed for 185 files.
- Ruff lint: passed.
- strict mypy: passed for 168 source files.
- full pytest with statement/branch coverage: **445 passed, 0 failed, 0 skipped; 85% overall**.
- focused CRA-67 unit suite: **115 passed, 0 failed, 0 skipped**.
- focused real-PostgreSQL Final Exam acceptance: **1 passed, 0 failed, 0 skipped**. It proves 20
  feedback-free saves, 14/20 = 70%, one critical error, one real finish plus one same-key replay,
  certification/history and canonical Admin result projections.
- final combined Admin assessment API plus Final Exam PostgreSQL evidence rerun: **5 passed, 0
  failed, 0 skipped**.
- The 445-test full rerun started before the new evidence-only integration file existed; therefore
  that file is reported separately rather than being misrepresented as part of the 445 collection.
- Alembic `upgrade head`, `current --check-heads` and `check`: passed at
  `0014_practice_persistence`; no new upgrade operations detected.

## Frontend and browser gate

- Prettier, ESLint and TypeScript project checking: passed.
- Vite production build: passed.
- full Vitest: **57 passed, 0 failed, 0 skipped**.
- full Playwright regression: **21 passed, 0 failed, 0 skipped** across 1440×1000 Admin desktop,
  768×1024 compact and 375×812 Employee mobile projects.
- After the final certification-copy correction, focused component tests report **2 passed** and
  the complete Final Exam browser journey reports **3 passed** across the same three projects.
- The journey proves 20 questions, no feedback before finish, explicit confirmation, a 14/20 pass,
  certification only after submission, no passed-state retake and no horizontal overflow.

## Security and limitations

- Employee tenant/location/profile authority remains session-derived. Admin result reads remain
  Organization-scoped and preserve existing MFA/RBAC guards.
- Pre-finish responses contain no grading payload, explanation or correctness. Finish remains
  idempotent under a real concurrent same-key PostgreSQL race.
- The candidate adds no migration, dependency, provider call, worker, deployment, production
  configuration, leaderboard or separate certification persistence.
- Automated question sourcing remains limited to verified structured menu facts. Preparation order
  and serving/assembly questions remain excluded because current sources do not prove them.
- Slice 8 Attention/Retakes administration, pilot access/admin/content closure and real Bacara
  ingestion remain outside CRA-67.

## Local checkpoint boundary

1. `6be8f4d` — readiness and balanced pool.
2. `c56401e` — eligibility and attempt lifecycle.
3. `fb1b790` — feedback-free answer saves.
4. `d0f18d4` — atomic finish and certification results.
5. `f28c9bd` — canonical Admin result read models.
6. `2f68844` — Admin Final Exam readiness and Results UI.
7. `3038810` — Employee Final Exam experience.
8. This documentation/evidence checkpoint — acceptance matrix, browser journey and regression
   closure; its exact hash is recorded after the local commit.

No CRA-67 commit has been pushed. Acceptance, a Linear evidence comment, ordinary push, PR, merge,
provider and deployment each remain separately authorized actions.
