# CRA-288 optional menu preparation

Extends the existing versioned MenuItem with optional volume, technique, glassware,
garnish, serving standard and preparation time. Existing ingredient/allergen data and
Waiter behavior are preserved. No restaurant recipes or policy values are invented.
Private illustrated lessons continue to use the existing Training asset workflow.

RED: structured preparation was rejected by the API (422); employee rendering and
human-readable audit history assertions failed before their implementations.
GREEN: 68 backend tests passed, 0 failed/skipped (147.48s), covering preparation,
admin/import/publication/employee menu, operations and migrations. The preparation
regression covers publication, draft copy, partial update, clearing, history and
published employee visibility. Three frontend files: 25 tests passed, 0 failed.

Ruff format/check, mypy (278 files), TypeScript, ESLint, Prettier and diff whitespace
checks passed. Alembic is at 0025_menu_preparation; metadata check reports no drift.
The additive nullable migration preserves old rows; downgrade refuses populated data.
Fresh review checked partial PATCH preservation, history serialization, server validation,
draft-only writes through existing guards and scoped employee reads.

Full repository acceptance remains pending Academy implementation. No push, deployment
or merge was performed; tests used only the approved CRA-288 local test database.
