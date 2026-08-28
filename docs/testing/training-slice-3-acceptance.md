# MVP Vertical Slice 3 — Training Content acceptance evidence

**Bounded issue:** [CRA-54](https://linear.app/craftspacee/issue/CRA-54)  
**Planning authority:** accepted CRA-53  
**Evidence date:** 2026-08-28  
**State:** accepted, Done, and fast-forward published through `d955f6a`

Linear remains canonical for product, API, data, RBAC, and acceptance contracts. This document
records the repository evidence that actually ran. Denys accepted CRA-54 and authorized publication
of its nine checkpoints. Railway, provider, deployment, and production smoke were not executed.

## Implemented boundary

- Location-owned versioned Training persistence at Alembic head `0008_training_content`.
- One fixed `menu` Module per Training Version, stable lesson identity, ordered Lessons, and seven
  strict content block types: heading, text, list, callout, Menu Item card, private image, and
  allowlisted external YouTube video.
- One mutable Draft and one current Published version per Location, optimistic revision checks,
  immutable Published versions, and atomic previous-version archive on publication.
- Private image upload intent, verification, archive, and five-minute signed read access through
  the existing storage boundary; fake storage only in automated tests.
- MFA-, tenant-, Location-, CSRF-, revision-, and where required idempotency-protected Admin API.
- Readiness validation for canonical Ukrainian content, required lesson blocks, current Published
  Menu dependency, Menu Item links, private image readiness/alt text, video identifiers, and stale
  revision/dependency state. English translation state remains warning-only.
- Active Employee read-only reference API derived from the own Profile Location. It exposes only
  the current Published Training version with entity/block locale fallback and no Draft,
  provenance, storage key, checksum, tenant selector, or revision fields.
- Responsive Admin authoring workspace and mobile-first Employee Module → Lesson editorial reader.
  Save/conflict/upload states are announced, reorder actions have button/keyboard parity, images
  preserve alt text, and video embeds use a hardcoded `youtube-nocookie.com` origin without autoplay.

Assignments, completions, progress, rollout, notifications, Practice, exams, analytics, provider
calls, deployment, and production configuration remain outside Slice 3. Publication returns
explicit zero counts for those Slice 4 concerns, and no completion route exists.

## Requirement evidence

| Requirement                                         | Evidence                                                      | Result |
| --------------------------------------------------- | ------------------------------------------------------------- | ------ |
| Versioned Training graph and tenant ownership       | model, constraint, and migration tests                        | Passed |
| Fixed Menu Module and Draft copy semantics          | Training draft service tests                                  | Passed |
| Revision-guarded Module/Lesson CRUD and reorder     | service and protected Admin API tests                         | Passed |
| Seven strict content block types                    | schema unit tests and content service tests                   | Passed |
| Private bounded image lifecycle                     | private storage, asset service, and Admin API tests           | Passed |
| Readiness and current Menu dependency               | Training publication API tests                                | Passed |
| Atomic publish, replay, race, archive, and rollback | PostgreSQL publication tests                                  | Passed |
| Published-only Active Employee reference            | Employee Training API and asset-access tests                  | Passed |
| Locale fallback without internal state exposure     | Employee API/OpenAPI tests                                    | Passed |
| Admin authoring, upload, conflict, reorder, publish | Testing Library plus Playwright                               | Passed |
| Employee Module and Lesson reader                   | Testing Library plus Playwright                               | Passed |
| No Slice 4 behavior                                 | API schema/OpenAPI, zero-count publication, UI assertions     | Passed |
| Head and metadata agreement                         | empty-database test, `current --check-heads`, `alembic check` | Passed |

## RED → GREEN evidence

The final Employee frontend checkpoint began with focused failing tests. Vitest could not resolve
the three Employee Learning page modules, and the existing `Навчання` shell destination was still
a disabled button instead of the expected link. This was the intended missing behavior, not a
broken environment.

GREEN adds the three protected routes, typed reference contracts, responsive pages, safe rendering
for all seven block types, signed image access, the allowlisted video embed, and the enabled bottom
navigation destination. The focused rerun reported 5 passed, 0 failed. A later lint pass identified
only React effect-boundary declarations; the final implementation documents the server-snapshot
invariant and passes the complete lint/type gate.

Earlier CRA-54 backend checkpoints likewise followed RED → GREEN for persistence, draft workflow,
typed blocks, private assets, Admin API, atomic publication, and Employee reference behavior. No
knowingly broken RED state was committed.

## Backend gate

The exact commands from [`.harness/TESTING.md`](../../.harness/TESTING.md) ran with Python 3.12.10
against the guarded native PostgreSQL 16 test database:

- Ruff format check: passed, 134 files already formatted;
- Ruff check: passed;
- strict mypy: passed, 123 source files checked;
- pytest: 318 passed, 0 failed, 0 skipped;
- overall statement/branch coverage: 88%;
- predeclared seven-file critical Training set: 80% aggregate statement/branch coverage;
- Alembic current head: `0008_training_content`;
- empty-database upgrade, Training migration downgrade/upgrade, `current --check-heads`, and
  metadata no-drift: passed.

The predeclared critical set is:

- `app/api/routes/training.py`;
- `app/services/training_drafts.py`;
- `app/services/training_content.py`;
- `app/services/training_assets.py`;
- `app/services/training_publication.py`;
- `app/services/employee_training.py`;
- `app/services/private_storage.py`.

## Frontend and browser gate

The complete local frontend gate used the repository Node.js 24 / pnpm 11 boundary:

- Prettier, ESLint, TypeScript, and Vite production build: passed;
- Vitest/Testing Library: 27 passed, 0 failed, 0 skipped across 14 files;
- Playwright: 9 passed, 0 failed, 0 skipped;
- production bundle: 48 modules, 323.38 kB JavaScript (93.87 kB gzip) and 31.80 kB CSS
  (7.05 kB gzip).

Playwright runs three route-mocked business paths in each approved project: 1440×1000 Admin
desktop, 768×1024 Admin compact, and 375×812 Employee mobile. The new CRA-54 path proves Admin
readiness and confirmed publication, then reloads as an Active Employee and reads the current
Module and Lesson, including private image alt text, Menu Item card, and reduced-motion-safe video.

## Security and final inventory review

- Admin writes retain same-Organization and Location filters, MFA, CSRF, revision checks, and
  required idempotency keys.
- Employee reads derive tenant and Location from the own Active Profile and are non-enumerating.
- Published references omit Draft/revision state, internal translations, storage keys, checksums,
  audit actors, and caller-selected tenant identifiers.
- Arbitrary HTML and arbitrary iframe URLs are never rendered. React escapes copy; YouTube embeds
  are reconstructed from the validated 11-character identifier and a fixed privacy origin.
- `.env*`, credentials, local paths, caches, coverage data, Playwright artifacts, and runtime output
  are excluded from staging.
- Protected untracked `Photos/` and local untracked `outputs/` were not modified or staged.

## Acceptance, publication, and next gate

- Browser acceptance uses deterministic API route mocks. Real persistence, tenant isolation,
  concurrency, rollback, and migrations are proved separately by the PostgreSQL backend gate.
- Storage behavior is tested with the fake private adapter; no paid or external provider was called.
- Denys accepted CRA-54 and authorized fast-forward publication of the nine-checkpoint range
  `8e15bd2..d955f6a`; remote verification confirmed `origin/main` at `d955f6a`.
- No Railway/runtime smoke, deployment, production configuration, PR, merge, or history rewrite
  was performed.
- The next product step is a separate bounded Slice 4 planning issue. Runtime/provider validation
  remains separately gated.
