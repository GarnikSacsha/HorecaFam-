# CRA-237 — grouped readiness and explicit demo publication

Denys approved both improvements after the imported snapshot exposed repeated
FACTS_UNCONFIRMED blockers. Canonical issue: https://linear.app/craftspacee/issue/CRA-237.
The FINAL CRA-12 document has the accepted explicit non-production exception.
The initial implementation was local only; the subsequently authorized delivery and demo
publication are recorded below. No source commit was performed.

## Result

Readiness groups matching code/message/entity kind into one row with counts and a collapsed,
scroll-bounded affected-item list. Loaded items show names; others show stable IDs and load on
request through the existing scoped detail API. Focus moves to the item; pagination remains
intact. Generation guards discard navigation responses after a workspace change.
UA item-translation findings now use stable item IDs consistently with the detail route.

Normal publication is unchanged. Readiness adds demo_publication_allowed, true only when all
blockers are FACTS_UNCONFIRMED in development/test/staging. The new request flag
`demo_with_unknown_facts` defaults false. Production rejects it with 403
DEMO_PUBLICATION_FORBIDDEN. Explicit demo publication preserves all fact states/lists and
verification metadata and waives no other blocker. Mode participates in idempotency; ordinary
fingerprints remain compatible with earlier requests. Audit records the explicit flag.
No migration or new configuration is required. This is an environment-bound publication
exception, not a portable certification or a persisted menu mode.

The UI requires acknowledgement tied to the current Draft ID/revision and a confirmation dialog.
Unknown facts are never converted to confirmed_none. Existing question-generation guards require
confirmed/verified component/allergen data; category/description behavior is preserved.

## Ordered local boundaries and paths

The initial grouping and demo stages share UI files. For any later authorized selective commits,
use these coherent final boundaries, without staging unrelated source or customer artifacts:

1. Backend: app/api/routes/menus.py, app/schemas/menu.py, app/services/menu_publication.py,
   tests/api/test_menu_publication_api.py (under backend/). Outcome: explicit bounded demo
   publication and stable readiness item navigation. Gate: PostgreSQL publication/import/Admin/
   Employee tests, schema/generation units, Ruff/mypy.
2. Frontend: src/admin/AdminMenuLifecyclePanel.tsx and its test, src/admin/AdminMenuPage.tsx,
   src/api/contracts.ts, src/styles.css, e2e/menu-demo-publication.spec.ts (under frontend/).
   Outcome: grouped findings, item navigation and explicit demo opt-in. Gate: Vitest, browser
   checks in three viewports, formatting/lint/types/build.
3. Evidence: this report, menu-fact-confirmation-workflow.md and STATUS.md.
   Gate: exact result/link/diff/inventory review. No local-commit approval is inferred.

## Verification

- Grouping RED: 1 failed, 2 passed — 308 repeated messages instead of one group.
- Demo UI RED: 1 failed, 3 passed — acknowledgement absent.
- Backend demo RED: 3 failed, 6 deselected — missing capability/explicit exception.
- Stable translation-link RED: 1 failed, 8 deselected — version-item ID instead of stable ID.
- Backend adjacent GREEN: 78 passed, 0 failed/skipped, 86.09 s. Publication/import/Admin/
  Employee API, menu schemas and deterministic question-generation units.
- Full frontend GREEN: 114 passed in 26 files, 0 failed/skipped, 48.93 s.
- Playwright: 3 passed, 0 failed/skipped, 9.4 s (1440x1000, 768x1024, 375x812), mocked APIs.
  Verified compact grouping, unloaded item navigation/focus, explicit acknowledgement and
  publish payload, no horizontal overflow; inspected the mobile screenshot.
- Frontend lint/types/build passed; existing bundle warning remains (504.33 kB).
- Backend Ruff and strict mypy passed (239 source files).

One initial adjacent command named a nonexistent test file and collected zero tests; corrected
command ran the 78-test selection. One initial new assertion assumed a nested error envelope;
corrected it to the existing top-level code after verifying the actual API contract. These are
setup/test-authoring failures, not claimed product RED. No full backend coverage rerun.
Final publication follow-up after stable-ID correction: 9 passed, 0 failed/skipped, 27.71 s.
The same 9 tests passed from the isolated CRA-237 candidate itself in 28.74 s.
These overlap earlier coverage and are not additional distinct-test totals.

## Future source-based confirmation

See [the concrete confirmation workflow](menu-fact-confirmation-workflow.md). The current Admin
item editor only edits name/price; full fact confirmation UI is not implemented by this task.
Its existing manual-create confirmed_none defaults also need correction in that bounded work.
No false confirmation of the imported snapshot is authorized or performed.

## Release boundary

Prepare the candidate from the previously verified CRA-233 source plus only the mapped CRA-237
files. Keep CRA-234 outside this rollout candidate; it remains separately local. Deployment of
API/web needs separate approval. Do not reimport the existing menu or publish before the new
behavior is delivered and readiness is freshly inspected. No worker/cron/migration change needed.


## Final review and candidate

Separate read-only review checked environment authority, default strict behavior, exact waiver
allowlist, immutable facts, audit/idempotency, existing MFA/CSRF/tenant dependencies, revision
revalidation and UI navigation generation guards. No additional blocking defect was established.
The UI has no authority to select server environment or waive other readiness codes.

Candidate: outputs/cra-237-candidate-2026-09-16/source.zip, 385 files, ten explicit overlays.
SHA-256: 65469ea9efee6847607721fb4db61bae6dc9be2c98f390e87a93131d614f97be.
Manifest recheck: zero mismatches/extras after removing generated test bytecode only.
Frontend source matches the tested checkout after normalizing CRLF/LF; initial byte-exact
comparison flagged these line endings, not different application code. Package excludes CRA-234.
No hosted operation or local Git commit was performed. The Git index remains unchanged.


## Authorized staging delivery and demo publication — 2026-09-16

Denys explicitly approved deploying this exact package to existing staging API/web and
publishing the existing imported Draft as demo. Before upload, all 385 manifest files and
ZIP SHA-256 matched; API APP_ENV was verified as staging. Previous API/web deployments
were SUCCESS. Railway up used the isolated source directory with path-as-root and explicit
project/environment/service selection; the dirty repository root was not uploaded.

- API deployment: 180b0d82-c1cb-476a-baff-76d5575293ec, SUCCESS.
- Web deployment: 6483f10e-8014-40f5-b2d5-45d0ef64172b, SUCCESS.
- HTTP checks: 4 passed, 0 failed/skipped: web health, API health, Admin Menu return 200;
  missing asset returns 404. Both referenced JS/CSS assets return 200 and match the tested
  build names index-ExuJSWtR.js and index-c_AN5TjU.css.
- Fresh authenticated UI: existing Draft v1; one collapsed FACTS_UNCONFIRMED group with
  308 affected items, demo acknowledgement initially unchecked and publication disabled.
- Checked explicit demo acknowledgement, opened the named confirmation dialog, and confirmed
  once. Result: Published Menu v1 and no Draft. No reimport or duplicate publication occurred.
- The demo path preserves unknown facts; it does not certify ingredients/allergens. Full source
  confirmation editor and Employee training journey remain separate work. Browser confirmation
  verifies publication, not a full employee acceptance test.

No worker, cron, remote setting, migration, Git commit/push or CRA-234 rollout occurred.
The initial sandbox network read failed; the authorized network-enabled read and delivery
succeeded. Local deployment smoke evidence: outputs/cra-237-candidate-2026-09-16/http-smoke.json.
