# MVP Vertical Slice 5 — Interactive Training accepted evidence

**Bounded issue:** [CRA-61](https://linear.app/craftspacee/issue/CRA-61)  
**Canonical plan:** [CRA-60](https://linear.app/craftspacee/issue/CRA-60)  
**Evidence date:** 2026-08-29  
**Status:** accepted and Done locally as `93ce970..614da3d`; CRA-62 governs publication evidence

This record maps the mandatory 27-scenario Slice 5 gate to evidence that actually ran. It does
not replace the Linear contracts and makes no acceptance, push, deployment, provider, PR, or merge
claim.

## Delivered boundary

The ten local implementation checkpoints add versioned Question Candidate and Question Bank
persistence, deterministic source-bound category, component, allergen and description generation,
human review/publication, per-Lesson readiness, five-question immutable Interactive Training
Attempts, progressive idempotent Answers, immediate feedback, device takeover, Results,
Latest/Best history, Admin review/readiness UI and the Employee mobile flow. Alembic
`0013_question_templates` makes all four active rules available after a clean upgrade; runtime
generation no longer depends on manual test or operator seeding.

Interactive Training remains distinct from Slice 6 Practice and Slice 7 Final Exam. It creates no
Passed/Failed state and never mutates Lesson Completion, Training Progress, certification, or exam
eligibility.

## Mandatory scenario matrix

| # | Accepted scenario | Executable evidence | Result |
| -: | --- | --- | --- |
| 1 | PostgreSQL schema, constraints, indexes and clean upgrade | persistence contract, migration tests through `0013_question_templates` | Pass |
| 2 | Source-supported deterministic Candidates with exact rule/version/provenance | question-generation unit and integration suites | Pass |
| 3 | Idempotent regeneration; ambiguity and price-only exclusions | question-generation unit/integration suites | Pass |
| 4 | Source changes stale new-use Questions without changing snapshots | generation and Attempt integration suites | Pass |
| 5 | Protected review; stale/unsupported edits and partial batch rejection | Admin API, review unit and generation integration suites | Pass |
| 6 | Approval creates immutable Question Version, pool, audit and readiness | generation/review integration suite | Pass |
| 7 | No pre-feedback grading key, correct flag, explanation or unsafe provenance | Admin OpenAPI/API and Attempt response tests | Pass |
| 8 | Blocked/Warning/Ready readiness and useful Lesson access | readiness unit, review and history suites | Pass |
| 9 | Completion, current Assignment and Active participation gate start | history/Attempt integration and Employee component suites | Pass |
| 10 | Exactly five compatible coverage-first immutable snapshots | Attempt integration suite | Pass |
| 11 | Replay/concurrent start preserves one active Attempt/snapshot | persistence and Attempt integration suites | Pass |
| 12 | Question Bank staleness cannot rewrite an active Attempt | Attempt integration suite | Pass |
| 13 | Typed, CSRF/idempotency-protected immutable Answer | answer API/schema/service tests | Pass |
| 14 | Feedback only after confirmed save and only for that Question | answer integration and Employee component suites | Pass |
| 15 | Resume opens the next unanswered Question unchanged | Attempt/answer integration and Employee component suites | Pass |
| 16 | Fifth Answer completes once; forced failure rolls back | answer integration suite | Pass |
| 17 | Exact Knowledge, no Passed/Failed, Progress or eligibility mutation | grading/history integration and Employee component suites | Pass |
| 18 | Latest, Best and bounded/full history are distinct | history integration suite | Pass |
| 19 | Pause/Disabled/non-rollout writes denied without history loss | answer/history integration and Employee component suites | Pass |
| 20 | Rollout-lineage Attempt remains old-Version history | history and Assignment integration suites | Pass |
| 21 | Locale switch preserves the snapshotted Attempt locale | Attempt and Employee component suites | Pass |
| 22 | Takeover preserves Answers and revokes the old lease generation | Attempt and Employee component suites | Pass |
| 23 | Foreign IDs are non-enumerating and mutation-free | Admin API, history and Attempt integration suites | Pass |
| 24 | Admin queue/review/readiness/stale/batch UI | `AdminQuestionBankPage.test.tsx` | Pass |
| 25 | Employee availability/Attempt/feedback/retry/resume/Result/history/Pause/takeover UI | `EmployeeInteractiveTraining.test.tsx` | Pass |
| 26 | Three-viewport Admin generation/review → Employee five-answer completion | `e2e/interactive-training-slice.spec.ts` | Pass |
| 27 | Full regression, coverage, migrations, frontend and inventory | commands and results below | Pass |

## Backend gate

Environment: Python 3.12.10, native PostgreSQL 16, ignored test-only environment, no SQLite.

- Ruff format and lint: passed.
- strict mypy: passed for 158 source files.
- full pytest control run: **424 passed, 0 failed, 0 skipped**.
- coverage-instrumented full run: **88% overall statement/branch coverage**.
- predeclared five-file critical Slice 5 aggregate: **86%** across question generation, question
  review, Attempt, Answer and history services.
- focused amendment gates: **10 unit tests passed** plus **2 PostgreSQL tests passed** for generation
  and the new migration round trip.
- migration suite: **13 passed**; current head `0013_question_templates`; clean upgrade, downgrade/
  upgrade and candidate-provenance/template round trips passed.
- Alembic current-head and autogenerate checks passed with no new upgrade operations.

## Frontend and browser gate

- The current worktree and clean dependency-bearing checkout had identical `frontend` Git tree
  `d1b7e3c4f5155b241e046e9c8efe3fe2a381cc97`; successful frontend commands ran against that clean
  checkout because this worktree has no `node_modules`.
- Prettier, ESLint and TypeScript project checking: passed.
- Vitest: **16 files passed; 45 tests passed, 0 failed, 0 skipped**.
- Vite production build: passed; 52 modules transformed.
- Playwright: **15 passed, 0 failed, 0 skipped** across 1440×1000, 768×1024 and 375×812.
- The new browser case performs exact-version generation, opens provenance, approves the
  Candidate, starts an Employee Attempt, confirms all five Answers and renders the final Result.
- Playwright uses deterministic route mocks for the browser contract/UI boundary; real
  PostgreSQL behavior is covered by the backend integration gate.

## Security, inventory and limitations

- Admin review remains server-authoritative for MFA, RBAC, Organization/Location scope, CSRF,
  expected revision and idempotency. Employee identity and ownership come from the Session.
- Correct flags and grading payloads stay hidden until the corresponding Answer is confirmed.
- `0012_question_rules` seeds deterministic `menu.category` version 1 (`single_choice`), and
  `0013_question_templates` seeds `menu.components` version 1 (`multiple_choice`),
  `menu.allergens` version 1 (`recognition`) and `menu.description` version 1 (`recognition`).
- Component generation requires `confirmed_present`, verified item/link facts, at least two
  correct components and one unambiguous distractor. Allergen generation requires
  `confirmed_present`, verified item/link facts and a distractor. Description generation requires
  ready, verified and case-insensitively unique Ukrainian names and non-empty descriptions.
- Unknown, `confirmed_none`, unverified, ambiguous and duplicate-label facts remain excluded.
  Ordering/assembly and matching execution stay typed, but automated templates are not claimed:
  component position proves display order, not preparation order, and no verified pair model exists.
- Provider/staging/deployment smoke is deferred by the accepted gate. No provider call,
  dependency, architecture change, production mutation, deployment, push, PR, merge or history
  rewrite occurred.
- Protected `Photos/` and local `outputs/` remain untracked, untouched, unstaged and unpublished.

## Acceptance and publication boundary

Denys explicitly accepted this multi-template evidence and its remaining source-bound limitation.
CRA-61 is Done. CRA-62 governs repository synchronization, ordinary publication and exact remote
evidence. PR, merge, deployment and provider activity remain separate approval gates.
