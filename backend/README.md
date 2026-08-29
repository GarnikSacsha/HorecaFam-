# Backend Foundation

This directory contains the accepted and published backend MVP Vertical Slice 1 through CRA-40
plus the accepted CRA-49 Menu Source of Truth runtime and corrective acceptance tail, published
through `8028d6e`. CRA-49 adds Location-owned versioned Menu persistence,
Draft/import/publication administration, and a published-only Employee reference API. Accepted
CRA-54 additionally implements Location-owned versioned Training Drafts, typed lesson content,
private images, atomic publication, and a published-only Employee Training reference API. Its nine
checkpoints are published through `d955f6a`. Accepted CRA-57 adds version-owned Role audiences,
immutable Assignment history, explicit Lesson Completion, derived current Progress, deterministic
replacement-Version Rollout, transactional provider-free notification jobs, Admin assignment and
rollout controls, and assignment-aware Employee Learning. Its nine checkpoints are published
through `d4e0184`, with the CRA-58 documentation checkpoint at `5dc459b`.

CRA-61 Interactive Training is now a local acceptance candidate. It adds assessment persistence
through Alembic head `0012_question_rules`, deterministic provenance-bound category Candidate
generation, Admin review/publication/readiness, immutable five-question Attempts, progressive
idempotent Answers with immediate feedback, Results and topic history. It is not yet accepted or
published.

Python 3.12 and PostgreSQL 16 are the approved runtime versions.

Before backend work, read [`AGENTS.md`](AGENTS.md) and the repository
[`../AGENTS.md`](../AGENTS.md). Linear remains canonical for product/API/data/test-stage
contracts.

## Local setup

From the repository root:

```powershell
rtk py -3.12 -m venv .venv
rtk .\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
```

Real PostgreSQL 16 is required for integration and migration tests. Two local boundaries are
supported:

- Docker Compose through `compose.test.yml` when Docker is available.
- Native PostgreSQL 16 as the accepted local fallback.

Keep local values only in ignored `.env` or `.env.test` files. Use obvious placeholders when
creating the test configuration; never commit or print the real URL:

```dotenv
APP_ENV=test
TEST_DATABASE_URL=<local-test-postgresql-async-url>
DATABASE_URL=<same-local-test-postgresql-async-url>
```

Use only the dedicated test database when running destructive test setup or cleanup. Follow the
secret-safe environment loading procedure in
[`../.harness/TESTING.md`](../.harness/TESTING.md).

The application is exposed through the factory `app.main:create_app`; configuration is required
and there is no SQLite fallback. SQLAlchemy metadata covers identity/authentication records plus
invitations, API idempotency, invitation rate-limit buckets, background jobs, and email delivery
state, plus CRA-49 Menu versions, hierarchy, facts/provenance, deltas, import review, and publication
records, and CRA-54 Training versions, Modules, Lessons, translations, content blocks, assets, and
publication records, plus CRA-57 Training audiences, Assignments, Lesson Completions, Rollouts,
rollout rules, completion provenance, and transactional notification jobs. Alembic is the only
schema-management path; runtime and tests must not call `create_all`. The local CRA-61 candidate
adds Question Candidate/Bank, assessment configuration/readiness, Attempt/Answer/device lease and
Result history tables plus the active versioned category-generation rule.

## Quality and test commands

Run from `backend/`:

```powershell
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini current --check-heads
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

`assert_safe_test_database` rejects cleanup unless `APP_ENV=test` and the resolved database name is `horeca_test` or a worker-scoped derivative such as `horeca_test_gw0`.

The complete no-skip gate and accepted slice evidence index are documented in
[`../docs/testing/README.md`](../docs/testing/README.md).

The corrective accepted CRA-49 gate reports 270 passed, 0 failed, 0 skipped, 89% overall
statement/branch coverage, Alembic head `0007_menu_import_review`, and no metadata drift. It also
proves same-key/different-key Draft, Import Resolution/Confirm, and Publish concurrency plus stable
Employee Component search/cursor pagination. See
[`../docs/testing/menu-slice-2-acceptance.md`](../docs/testing/menu-slice-2-acceptance.md).

The accepted CRA-54 gate reports 318 passed, 0 failed, 0 skipped, 88% overall
statement/branch coverage, 80% aggregate coverage across the predeclared seven-file critical
Training set, Alembic head `0008_training_content`, and no metadata drift. It proves Draft and
publication races, replay, rollback, current Published Menu dependency, private storage boundaries,
published-only Employee access, and explicit zero Slice 4 effects. See
[`../docs/testing/training-slice-3-acceptance.md`](../docs/testing/training-slice-3-acceptance.md).

The accepted CRA-57 gate reports 363 passed, 0 failed, 0 skipped, 88% overall statement/branch
coverage, 87% aggregate coverage across the predeclared Slice 4 service set, Alembic head
`0009_assignment_completion_rollout`, and no metadata drift. It proves applicability and
Assignment concurrency, explicit idempotent Completion, assignment-aware current Progress,
retained-Version access, deterministic Rollout preview/confirm, stale-preview rejection, atomic
rollback, and provider-free transactional jobs. Practice, Question Bank, Knowledge Check, Final
Exam, Results, provider delivery, staging, and deployment remain outside the accepted Slice 4
boundary. See
[`../docs/testing/training-assignment-slice-4-acceptance.md`](../docs/testing/training-assignment-slice-4-acceptance.md).

The local CRA-61 candidate gate reports 417 backend tests, 88% overall statement/branch coverage,
85% aggregate coverage across the predeclared five critical Slice 5 services, Alembic head
`0012_question_rules`, and no metadata drift. Exact scenario mapping, frontend evidence and the
pending acceptance limitation are in
[`../docs/testing/interactive-training-slice-5-acceptance.md`](../docs/testing/interactive-training-slice-5-acceptance.md).
