# Menu Source of Truth Slice 2 — CRA-49 Acceptance Evidence

## Status and boundary

This document records the CRA-49 implementation accepted by Denys on 2026-08-28. Its original ten
implementation checkpoints end at `22927f7`, and the corrective acceptance tail is fast-forward
published on `origin/main` through `8028d6e`. No PR, merge, deployment, provider call, production
configuration, force-push, or history rewrite was performed.

The accepted implementation provides one Location-owned, versioned Menu Source of Truth; explicit
Draft editing; bounded JSON preview/review/confirm; atomic publication; and a published-only
Employee reference experience. Linear remains canonical for exact product, API, data, RBAC, and
acceptance contracts.

## Requirement-to-evidence matrix

| CRA-49 boundary | Automated evidence | Result |
| --- | --- | --- |
| Versioned Menu persistence and Location ownership | model constraints, migration round-trips, real PostgreSQL integration tests | Passed |
| One Draft and one current Published version | draft service and concurrent uniqueness tests | Passed |
| Revision-guarded hierarchy and item editing | service and protected Admin API tests | Passed |
| Facts, provenance, delta, and Training impact | schema and item-service tests | Passed |
| Safe JSON preview/review/confirm | import API, limits, RBAC, idempotency, blocker, and OpenAPI tests | Passed |
| Atomic publication and archive transition | readiness, rollback, idempotency, race, and second-publication tests | Passed |
| Zero Training applicability for Slice 2 | publish response and persisted publication tests | Passed |
| Published-only Employee reference | Active Profile/Location, search/filter, locale fallback, detail, and no-provenance tests | Passed |
| Admin editing/import/publication UI | Testing Library plus Playwright JSON review → publish path | Passed |
| Employee mobile search and detail UI | Testing Library plus Playwright Admin publish → Employee reference path | Passed |
| Migration head and metadata agreement | empty-database migration tests, `current --check-heads`, and `alembic check` | Passed |

## RED → GREEN evidence

Behavior checkpoints followed the repository RED → GREEN rule and never committed a knowingly
broken RED state. The final frontend checkpoint added a failing Employee shell assertion first:
the expected enabled `Меню` destination was absent and the shell still rendered only the four
first-slice destinations. GREEN adds `/employee/menu`, its published-only reference page, and
focused tests for search, section/category filtering, truthful no-publication state, locale
fallback, safe item detail, components, and allergens.

The first combined GREEN run found only a test-fixture omission: `LogoutButton` correctly required
a Router, while the new page fixture had not supplied one. Adding `MemoryRouter` corrected the
fixture without changing product behavior. The final component and browser gates are green.

The corrective closure added the missing real concurrency and Employee query evidence. Concurrent
same-key Import Confirm first reproduced `[200, 409]` in three of three controlled PostgreSQL runs:
the waiting request checked replay before the winner committed, then treated the confirmed Import
as non-ready after acquiring its lock. GREEN rechecks the idempotency record after the row lock in
Finding Resolution and Confirm. The identical reproducer then returned replay-safe `[200, 200]` in
three of three runs, while different keys retained one success and one conflict. Draft create and
revision mutation concurrency, verified Component search, deterministic cursor replay, second-page
ordering, and invalid-cursor rejection are also covered.

## Corrective coverage decision

Denys accepted the precise CRA-49 corrective gate on 2026-08-28: at least 80% overall backend
coverage with branch tracking, every mandatory Slice 2 scenario mapped, and explicit
concurrency/security proof. The earlier phrase requiring 90% branch coverage for a "declared
critical Slice 2 set" did not actually declare such a set before implementation. No file list is
selected retroactively from the completed coverage result. The corrective gate is therefore
reported transparently through the complete overall measurement and scenario evidence below.

## Backend gate

The complete gate ran against the guarded native PostgreSQL 16 test database with Python 3.12.10:

- Ruff format check: passed, 113 files already formatted;
- Ruff check: passed;
- strict mypy: passed, 103 source files checked;
- pytest: 270 passed, 0 failed, 0 skipped;
- overall statement/branch coverage: 89%;
- Alembic: single current head `0007_menu_import_review`;
- empty-database upgrade, `current --check-heads`, migration downgrade/upgrade coverage, and
  metadata no-drift: passed.

## Frontend and browser gate

The complete frontend gate ran with the repository's Node.js 24 / pnpm 11 boundary:

- Prettier, ESLint, TypeScript, and Vite production build: passed;
- Vitest/Testing Library: 19 passed, 0 failed, 0 skipped across 12 files;
- Playwright: 6 passed, 0 failed, 0 skipped;
- production bundle: 44 modules, 293.46 kB JavaScript (88.22 kB gzip) and 24.67 kB CSS
  (5.83 kB gzip).

Playwright runs two route-mocked business paths in each of three projects: 1440×1000 Admin
desktop, 768×1024 Admin compact, and 375×812 Employee mobile. The CRA-49 path covers Admin login
and MFA, JSON preview, explicit finding resolution, confirm-to-Draft, readiness, confirmed atomic
publication, Active Employee published Menu search, and safe detail facts.

## Security and scope review

- Admin mutations remain MFA-, Organization-, Location-, CSRF-, revision-, and where required
  idempotency-scoped.
- Employee endpoints derive Organization and Location only from the single own Active Profile;
  the public contract exposes no tenant selector or internal provenance.
- Raw import payloads, checksums, actor IDs, internal review state, credentials, `.env*`, local
  paths, caches, and runtime output are excluded from the published inventory.
- Publication archives the previous current version and commits version, diff, audit, and
  idempotency state atomically.
- Training content, Assignments, and notifications remain explicit zero-applicability outputs.
- `Photos/` remains protected untracked CRA-19 material and was not modified, staged, or committed.

## Limitations and exclusions

- Browser acceptance uses deterministic API route mocks; real persistence, races, rollback, and
  migration behavior are proved separately by the complete PostgreSQL backend gate.
- Only the accepted JSON import boundary is implemented; spreadsheet/OCR/provider ingestion is
  outside CRA-49.
- Training content authoring, assignment generation, notification delivery, analytics, broader
  Employee lifecycle administration, deployment, and production provisioning remain outside this
  slice.
