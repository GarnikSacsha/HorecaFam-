# CRA-288 baseline and isolated session-clock prerequisite

Date: 2026-10-07. Issue: CRA-288 — Implement multi-position training, Runner/Bartender content and Academy.

## Source boundary

- Authoritative base: `7a7f6f369aba4c2e0bc38f749615e63645e50e20`, confirmed against remote main before branch creation.
- Branch: `feature/multi-role-training-content`, in a separate managed worktree.
- Existing uncommitted main and other worktree changes were preserved.
- No CRA-288 product implementation is included in this checkpoint.
- No push, merge, deployment, production/staging mutation or dependency installation was performed.

## Separately approved prerequisite

The existing MFA enrollment test returned HTTP 500 because session expiry used the supplied
application clock while `sessions.created_at` used PostgreSQL's current time. A clock more than
one session lifetime in the past violated `ck_sessions_expiry_after_creation`.

The minimal fix sets `created_at=now` in `create_session`. Expiry still uses the unchanged
90-day employee / 30-day elevated session lifetimes. MFA verification, throttling, cookie,
revocation and authorization rules are unchanged. No schema migration is needed.

Commit boundary: `fix(auth): use one clock for session creation and expiry`.

Mapped paths:

- `backend/app/services/sessions.py`
- `backend/tests/integration/test_session_clock.py`
- This baseline evidence file.

Focused verification: regression RED/GREEN, auth/MFA and related security tests, Ruff and
mypy. Acceptance verification: full backend coverage gates, Alembic and the frontend baseline
below. This prerequisite is independent of the subsequent CRA-288 implementation.

## RED → GREEN evidence

The new PostgreSQL regression test supplies 2000-01-01 UTC and covers both session lifetimes.
It checks persisted creation, last-seen, expiry and MFA timestamps after commit and refresh.

| Run | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| New regression, before fix | 0 | 2 | 0 |
| New regression, after fix | 2 | 0 | 0 |
| Auth/MFA and related security suite | 95 | 0 | 0 |
| Full backend baseline, including regression | 996 | 0 | 0 |
| Frontend Vitest: 32 files | 166 | 0 | 0 |
| Playwright: desktop, compact, mobile | 87 | 0 | 0 |

The focused runs are subsets of the full backend run, not additional unique tests.
The full backend run completed in 1825.66 seconds.

Earlier attempts interrupted for shared-test-database interference, incompatible database
case-folding, or diagnosis of the pre-existing MFA failure are not counted as successful
baselines. The successful full run used only the isolated database described below.

## Environment and commands

Backend: Python 3.12.10, native PostgreSQL 16, dedicated local database `horeca_test_cra288`
in a separate loopback-only test instance. UTF-8 encoding and Ukrainian Windows locale preserve
the existing case-insensitive Cyrillic search behavior. Crash durability was disabled
(`fsync=off`) only in this disposable test instance; no crash-recovery guarantee is claimed.
Test connection settings stayed in process environment; no credentials or connection strings
were committed. No other pytest database or process was reused or stopped.

Backend commands from `backend/`, with the approved test environment loaded:

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_session_clock.py -q -p no:cacheprovider
rtk ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --cov=app --cov-branch --cov-report=term-missing --tb=no
rtk ..\.venv\Scripts\python.exe -m coverage json -o .pytest_cache/cra288/baseline.json
rtk ..\.venv\Scripts\python.exe -m tests.coverage_gate .pytest_cache/cra288/baseline.json
rtk ..\.venv\Scripts\python.exe -m ruff check --no-cache .
rtk ..\.venv\Scripts\python.exe -m ruff format --check --no-cache .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini current --check-heads
rtk ..\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

The coverage JSON was generated from the same successful full run and remains in ignored cache.

| Gate | Result |
| --- | --- |
| Statement coverage | 12453/13188 = 94.43%, PASS |
| Branch coverage | 2281/2802 = 81.41%, PASS |
| Fixed critical aggregate | 1334/1487 = 89.71%, PASS |
| Ruff check | PASS |
| Ruff format check | PASS, 284 files |
| Strict mypy | PASS, 260 source files |
| Alembic upgrade / current | PASS, `0021_lesson_question_cycles` |
| Alembic metadata comparison | PASS, no new upgrade operations |

Frontend commands from `frontend/`:

```powershell
rtk pnpm --config.verify-deps-before-run=false test
rtk pnpm --config.verify-deps-before-run=false test:e2e
rtk pnpm --config.verify-deps-before-run=false typecheck
rtk pnpm --config.verify-deps-before-run=false lint
rtk pnpm --config.verify-deps-before-run=false format:check
rtk pnpm --config.verify-deps-before-run=false build
```

All passed. The command-line dependency-verification override reused the existing installation;
it did not alter dependencies or lockfiles. Playwright started its own server on an unused port.
The existing build warning about a minified JavaScript chunk exceeding 500 kB remains.
Browser tests use mock APIs and do not establish authenticated staging acceptance.

## Gate decision

The baseline is GREEN after the separately authorized session-clock fix. CRA-288 may now begin
under its own commit map. Admin UI/UX redesign, production/staging work and automatic merge into
main remain outside scope.
