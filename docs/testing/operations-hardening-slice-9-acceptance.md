# CRA-77 Operations and Hardening Local Acceptance Evidence

## Status and boundary

This document records the local CRA-77 candidate verified on 2026-09-01. Denys authorized the
accepted thirteen-checkpoint map and local checkpoint commits. This evidence does not mark CRA-77
Done and does not authorize push, PR, merge, deployment, provider calls, new dependencies,
production configuration, non-test data mutation, backup restore, or real-venue bootstrap.

The candidate adds the bounded Slice 9 closure:

- password recovery/change plus TOTP enrollment and one-time MFA recovery codes;
- Employee pause/resume, disable/reactivate and session revocation;
- durable leased background jobs, attempts, retry/backoff and scheduled maintenance;
- Organization-scoped audit reads and platform-operator job inspection/retry;
- structured redacted request/job correlation;
- a dry-run-first, idempotent one-venue bootstrap command;
- responsive security, Employee lifecycle, audit and operator interfaces;
- a synthetic invitation-to-passing-final-result acceptance chain.

Alembic head is `0018_job_runtime`. No provider SDK or parallel runtime was added.

## Executed final gate

| Gate | Result |
|---|---|
| Backend full PostgreSQL suite | 530 passed, 0 failed, 0 skipped in 1262.95s |
| Backend statement/branch coverage | 86% overall |
| Predeclared CRA-77 critical set | 81% aggregate |
| Ruff format | 229 files already formatted |
| Ruff check | passed |
| mypy | no issues in 208 source files |
| Alembic | upgrade/current/check green at `0018_job_runtime`; no new upgrade operations |
| Frontend formatting, lint, types, build | passed |
| Frontend Vitest | 72 passed, 0 failed, 0 skipped across 21 files |
| Frontend Playwright | 42 passed, 0 failed, 0 skipped |

The critical coverage set is `password_recovery.py`, `mfa_enrollment.py`, `employees.py`,
`background_jobs.py`, `background_job_handlers.py`, `maintenance.py`, `operator_jobs.py`,
`observability.py`, and `bootstrap_venue.py`.

## RED-to-GREEN and compatibility evidence

Focused RED evidence proved the intended missing boundaries before implementation: the frontend
could not import the absent Admin audit page, backend observability imports failed before the
structured logging module existed, and bootstrap integration imports failed before the operations
module existed.

The full gate then exposed stale test assumptions rather than production regressions:

- three old fixtures set `training_participation_status` directly without the matching
  `training_paused_at` invariant, or returned to Active without clearing it;
- the Attention/Retakes backfill test seeded current ORM objects only after downgrading to a schema
  predating the new Employee lifecycle columns;
- the exact metadata inventory omitted the new `job_attempts` table.

The fixtures now model the database invariant, the backfill test seeds source history before the
legacy-schema downgrade, and the inventory includes `job_attempts`. Focused reruns passed 2/2 and
19/19; the clean full rerun then passed 530/530, including the password-reset worker handler in its
normal suite order.

## Security and isolation review

- Recovery tokens, MFA secrets/codes, session cookies, database URLs and provider payloads are not
  returned by operator/audit APIs or written to structured logs.
- Logs use bounded allowlisted fields and redact sensitive key families; request, job and attempt
  identifiers remain correlatable.
- Organization audit reads are tenant-scoped. Operator job routes require active platform access,
  completed MFA and CSRF on retry mutations.
- Job payloads are closed by job type; attempts store controlled failure codes instead of raw
  exception text. Retry is leased, bounded and idempotent.
- Bootstrap validates an active platform operator, exact `Europe/Kyiv` timezone, one Organization,
  one Location and one initial Organization Admin. Advisory locking and stable keys make replay
  idempotent; dry-run performs no write.
- Every destructive test command required `APP_ENV=test` and a dedicated `horeca_test*` database.
  No `.env` value was printed or staged.

## Pilot and release limitations

The local candidate proves code and synthetic behavior only:

- no non-test bootstrap apply was executed and no real Bacara/customer record was created;
- no email provider, Sentry, Railway, storage provider or paid service was called or configured;
- backup retention and an isolated restore drill remain unverified provider work;
- staging load/performance has no accepted profile and was not run;
- real-venue content validation and UAT were not run;
- production smoke, deployment and rollback were not run;
- automated semantic/focus/responsive browser coverage passed, but manual screen-reader,
  contrast and reduced-motion review remains a separate acceptance activity.

These are explicit external or later acceptance gates, not silent passes.

## Authorized checkpoint map

1. `974feeb` — security recovery persistence.
2. `289bc50` — password recovery and change flows.
3. `5d58c28` — MFA enrollment and recovery.
4. `27114b2` — security recovery interfaces.
5. `1707603` — Employee lifecycle controls.
6. `f008c66` — Employee lifecycle administration.
7. `74ca298` — durable worker runtime.
8. `108aab3` — handlers and maintenance scheduling.
9. `6145727` — audit and operator APIs.
10. `b6625fe` — audit and operator interfaces.
11. `69b1aef` — structured runtime logging.
12. `ffb92e4` — pilot bootstrap and synthetic acceptance.
13. This documentation/hardening checkpoint records the clean full gate and compatibility fixes.

The range is local. Push and every external action remain separately gated.
