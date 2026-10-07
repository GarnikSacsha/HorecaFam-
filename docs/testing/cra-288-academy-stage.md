# CRA-288 optional Academy

Academy articles are independent of required Training completion. Admins with MFA can
create/edit/publish or return articles to Draft using CSRF, creation idempotency and
revision-guarded updates. Each article has an organization/location, slug, Ukrainian
title/summary/plain-text body, category, order, timestamps and one/multiple/all-position
audience. Future positions work without a new enum. Employee discovery, direct reads and
cover access require current active membership, location, publication and audience.

The explicit starter import creates 13 Draft articles: four general and three each for
Waiter, Runner and Bartender. Admin maps existing positions; repeat import skips existing
slugs and preserves edits. Generic educational copy does not invent local recipes or policies.
Private covers reuse the existing verified image upload workflow and 300-second access.
Linked assets cannot be archived. New composite foreign keys enforce tenant scope.
Migration 0026_academy is additive and refuses downgrade when articles would be lost.

Employee navigation adds Menu/Academy links while retaining the existing four bottom tabs.
The existing Admin shell gains a bounded article editor; no admin/dashboard redesign.
The reusable image uploader also serves the existing Training editor, whose tests remain green.

## Evidence

- RED: Academy creation returned 404 instead of 201; shell test failed on the missing Menu link.
- Backend focused suite: 47 passed, 0 failed/skipped (90.10s), including Academy, private assets
  and existing migrations. Additional populated-data downgrade guards: 2 passed (4.93s).
- API coverage checks publication, replay, CSRF, MFA, revisions, invalid/foreign roles,
  all-position and position-specific access, role/location changes, unpublication,
  pending/disabled denial, cover access and unchanged required Training progress.
- Frontend focused: 25 passed. Full frontend: 179 passed in 34 files (21.02s).
- New Playwright: 6 passed (10.9s). Full Playwright: 96 passed (1.2m), three viewports.
  Mobile article screenshot reviewed: readable content, reachable navigation, no horizontal overflow.
- Ruff format/check: 314 files; mypy: 285 files; TypeScript, ESLint, Prettier and production build passed.
  New browser assertions initially failed TypeScript because E2E's tsconfig excludes DOM globals;
  changed them to the repository's existing string-evaluation convention and reran checks.
- Alembic current/check: 0026_academy, no metadata drift.
- Separate fresh review covered transaction rollback, location serialization, idempotency,
  role/asset composite keys, archive/link locking, signed URL gating, text rendering and
  preservation of existing content/progress. No unresolved issue identified in this boundary.

The final full backend coverage run is separate and still pending at this checkpoint.
No push, production/staging migration, deployment or merge performed.
