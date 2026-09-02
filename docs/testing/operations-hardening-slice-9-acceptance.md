# CRA-77 Operations and Hardening Acceptance Evidence

## Status and boundary

This document records the CRA-77 candidate independently revalidated on 2026-09-02. Denys
authorized the thirteen-checkpoint implementation map and its local checkpoint commits. The fresh
gate, security review and browser accessibility review found no blocking defect. The implementation
therefore meets the local acceptance boundary, and CRA-77 is accepted and Done in Linear.

Acceptance does not authorize push, PR, merge, deployment, provider calls, new dependencies,
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
| Backend full PostgreSQL suite | 530 passed, 0 failed, 0 skipped in 1334.59s |
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

## Independent acceptance review

The 2026-09-02 review reread the active CRA-77 boundary and inspected the security, lifecycle,
worker, maintenance, operator, observability, bootstrap, migration and responsive UI paths closest
to the change. It confirmed:

- password recovery remains non-enumerating and uses hashed, expiring, single-use tokens;
- MFA enrollment, recovery-code consumption, session revocation, CSRF and RBAC remain fail closed;
- Employee pause/resume and disable/reactivate preserve lifecycle invariants and retake state;
- job claiming, lease ownership, attempts, retry/backoff and maintenance finalization are durable,
  bounded and idempotent;
- audit and operator reads remain tenant/platform scoped, and logs expose only allowlisted,
  redacted correlation fields;
- bootstrap is dry-run-first, validates its one-venue boundary and serializes idempotent apply;
- migrations `0016` through `0018` form one current head with no model drift;
- no High or Critical acceptance defect was found.

## Manual browser accessibility review

The responsive authentication and operations surfaces were reviewed through the browser
accessibility tree and keyboard interaction at the local Vite candidate:

- Login focus order is email, password, submit, then password-recovery link; Enter activates the
  focused control.
- Forgot-password, reset-password, MFA and MFA-recovery pages expose one main landmark, a named
  region, a level-one heading, labeled fields and reachable actions.
- Invalid submissions expose an active alert and link the summary to the invalid field. Following
  the link moves focus to that field; `aria-invalid` and `aria-describedby` are present.
- Admin audit, Employee lifecycle and operator job surfaces use named navigation/main regions,
  headings, status/alert semantics, responsive table/card labels and a modal confirmation dialog.
- The confirmation dialog traps Tab, initially focuses Cancel, closes on Escape and returns focus
  to the invoking control.
- Measured ordinary-text contrast is at least 5.78:1; primary action text is 10.28:1; headings and
  labels are 17.78:1; validation text and links are 6.69:1.
- The global reduced-motion media query collapses animation and transition duration to `0.01ms`
  with one iteration.

This is a browser accessibility-tree proxy, not a physical NVDA/JAWS session. Real-device assistive
technology and venue-network UAT remain release-readiness activities and are not represented as
completed.

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
- browser accessibility-tree, keyboard, contrast and reduced-motion review passed; physical
  screen-reader and real-device UAT remain unperformed.

These are explicit external or later acceptance gates, not silent passes.

The executable release, backup/restore, rollback and physical-UAT gates are itemized in
[`operations-hardening-slice-9-release-checklists.md`](operations-hardening-slice-9-release-checklists.md).

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
13. `ef74be4` — documentation/hardening evidence records the clean full gate and compatibility
    fixes.

The complete thirteen-checkpoint range is `974feeb..ef74be4` and remains local. Push and every
external action remain separately gated.
