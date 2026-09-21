# CRA-238 — bound menu item selection

Denys approved the bounded frontend correction after the live editor required raw item IDs.
The picker searches the exact Training Draft menu dependency through existing scoped Menu
GET endpoints, follows opaque cursor pagination and retains distinct item identities. Options
show name, section/category and source key (stable code/ID fallback). Ukrainian empty/loading/
retry states and a native labelled select support keyboard use. Selection is scoped to
organization, location, draft, dependency and lesson; it is cleared after successful insertion.
The unchanged write sends menu_item_card with menu_item_id, note_uk and expected_revision.
The initial implementation made no API/schema/backend change, dependency, hosted write, commit
or deployment. Subsequent authorized delivery and content operations are recorded below.

## Verification

- RED: 1 failed, 11 filtered/skipped; expected failure was the remaining raw ID textbox.
  Initial sandbox Vite spawn EPERM was a setup failure, not RED; elevated local run reproduced RED.
- Full frontend: 119 passed, 0 failed/skipped, 52.26 s. This preceded final test-only strengthening.
- Final focused picker/editor: 16 passed, 0 failed/skipped, 6.55 s; includes search, duplicate labels,
  opaque cursor, retry/empty, stale response, revision mismatch, lesson switch and submitted payload.
- Final Playwright: 3 passed, 0 failed/skipped, 5.7 s; desktop, compact and mobile mocked APIs.
  Inspected mobile screenshot. No hosted acceptance claim.
- Final ESLint and production TypeScript/Vite build passed; formatting check passed.
  Existing bundle warning remains, JS 507.66 kB. No backend suites rerun.
- Initial lint/build failures in new code/test typing were corrected. One strengthened test used
  an incorrect spaced accessible button name; corrected to the observed name, then 16 passed.

Separate review covered exact dependency URL, unchanged CSRF/revision mutation, disabled empty
selection, stale fetch cleanup, retry and page deduplication. No additional blocking defect
identified. The previously observed audience revision conflict remains outside this issue.

## Boundaries and release

1. Intended commit feat(admin): select training menu cards by name —
   frontend/src/admin/AdminTrainingMenuPicker.tsx and .test.tsx,
   AdminTrainingPage.tsx and .test.tsx, frontend/e2e/training-menu-picker.spec.ts.
2. Intended commit docs: record training menu picker verification — this report.
No index or commit change is authorized. Preserve CRA-237 and unrelated work.

Candidate is the verified CRA-237 source plus only these five frontend source/test paths,
388 files. Existing API requires no deployment. CRA-234 remains excluded. Web-only deployment
required separate explicit approval, subsequently granted and executed below. Existing hosted
lessons must not be recreated.
Candidate manifest and archive: outputs/cra-238-candidate-2026-09-16/.

ZIP SHA-256: 3bed9fcaf2f24e6d9b3c13ed3ef364e73534719c6ec37d36fc94e10a66cf2640


## Authorized hosted continuation and publication — 2026-09-16

The preceding task records explicit approval for the sealed CRA-238 web rollout and later
separate approval for Training publication. Web deployment
`28e00b65-1409-407f-98bb-cacfe43e845b` reached SUCCESS; API was unchanged.
The 388-file candidate and ZIP hash above were verified before upload. Five HTTP checks passed
(healthz, API health, content page and JS/CSS); the live picker found exact source-key options
by name and saved lesson cards. This is recovered delivery evidence, not a new deployment.

Four required lessons were populated for Ofitsiant: 26, 26, 12 and 24 blocks, totaling 88,
including 40 menu-card occurrences. Existing records and source ordering were preserved.
Audience reload resolved an observed stale revision after Menu binding; the underlying UI
conflict remains separate potential corrective work, not an unresolved publication blocker.
Readiness passed before the user separately approved publication. Final UI showed Published v1
and no Draft. No question generation or Employee assessment was verified in that operation.

The current reconciliation freshly checked public HTML: HTTP 200 and CRA-238 asset
`index-DEGtw7P2.js`. Authenticated content UI again showed Published v1/no Draft; Question Bank
showed no assessment configuration and an empty review queue. These reads do not establish
full regression, all historical candidate states, Employee assignment or Results acceptance.
Operational evidence is retained in the excluded local continuation report; customer content
is not copied into this tracked report. See [current continuation](demo-continuation-2026-09-16.md).
