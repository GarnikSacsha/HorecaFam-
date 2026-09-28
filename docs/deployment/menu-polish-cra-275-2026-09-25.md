# CRA-275 — prepared web delivery, 2026-09-25

## Delivered and verified — later 2026-09-25

Denys explicitly authorized this exact web-only deployment. The sealed packet was
reverified (135 source files, archive parity, zero extras/mismatches), uploaded to the
existing staging web service, built by its Dockerfile and reached SUCCESS as
`3b7d4c5c-fc69-40cc-a151-407091abd4cb`. Build log and /healthz passed. Public smoke:
10 passed / 0 failed / 0 skipped, including exact candidate JS/CSS SHA-256, SPA/API
routing, expected 404s, no-store HTML and immutable assets. No API deployment occurred.

Authenticated Admin loads card names successfully. Eight pairs were confirmed equal
by exact menu_item_id and menu_version_id, then only the redundant draft-v5 blocks
were removed under the existing cleanup scope. Readback after reload: Food31/45,
Dessert20/37, Other13/25, Drinks17/33 cards/blocks (81 cards total). Other and Drinks
remaining block text/order exactly matched their before snapshots minus selected
deletions, including variant companions. Readiness enabled, zero error alerts.
Published v4 remains active; no publication, assessment write or employee rollout.

Authenticated Employee bowl dialog now has 395 UAH, guest text, one seven-label allergen
list and original-description disclosure, without composition or source warnings.
Close restores focus to the original card. Home confirms assigned v4, 4/4 completion
and certification. No fresh attempt was started.

Browser control timed out during a batch of read-only disclosure clicks; reconnected
to the same Chrome profile in a new tab. A readback initially timed out while names
loaded; subsequent full inventory showed zero unresolved names. Neither interruption
was a failed application mutation. The first compact deployment-status formatter
selected an array incorrectly and returned nulls; direct first-entry read confirmed
the exact SUCCESS deployment before acceptance.

No commit or push. Source remains uncommitted; retain the sealed packet until the
reviewed Git checkpoint is separately authorized. Next gate: separately approve v5
publication, unchanged 60-question assessment recovery/readiness and two-employee
rollout preserving completions. Earlier preparation-only statements below are history.

## Outcome and authority

Denys asked to continue after local fixes and documentation reconciliation. This
step prepares a concrete web-only delivery for separate approval under AGENTS.md.
No upload, deployment, commit, push, content publication or rollout occurred.

The candidate contains the Employee dialog cleanup and Admin card identity display.
It does not change API contracts, backend, infrastructure, dependencies or data.
The unchanged draft v5 and published v4 remain as recorded in the
[current testing report](../testing/menu-detail-polish-2026-09-25.md).

## Exact candidate

Base: `60bf1599324040e62c5cea12725df17d111cdb50`, the fresh confirmed SUCCESS
deployment commit for both API and web. Export only tracked frontend files and apply
the eight reviewed source/test paths listed in the manifest. All other frontend
source matches the tested worktree after line-ending normalization.

Ignored local packet: `outputs/menu-polish-delivery-2026-09-25/source.zip`.
Manifest: `outputs/menu-polish-delivery-2026-09-25/manifest.json`.
Upload root after approval: its `source` directory, containing `frontend/` only.
135 files; SHA-256:
`f89e3d03195657f176c8639ea96de4980db66328568ec598108a2cd1747e4326`.

No environment files, secrets, dependencies, build output, Photos, Git metadata,
backend or local helper is in the source packet. Tests run against a separate
validation copy using existing dependencies; the source/ZIP stay unchanged.

## Verification and limitations

- Source manifest and archive: 135 files, zero mismatches or extras.
- Separate exact-candidate TypeScript and Vite build passed. Eight emitted artifacts
  match the corresponding working build byte for byte, including index.html and
  `index-CyBrlEEU.js`. Three obsolete working-directory JS bundles are absent from
  the clean candidate; the initial whole-directory comparison rejected those extras.
- Existing full frontend evidence remains 160 passed / 0 failed / 0 skipped; no
  additional complete test run is claimed in this packaging-only step. Earlier
  Employee browser evidence is 6/0/0; new Admin hosted acceptance remains pending.
- Existing over-500-kB JS warning remains. No Docker build ran locally.
- First packaging comparison failed on baseline CRLF normalization before writing
  source. Corrected comparison preserves baseline bytes and checks normalized parity.
  A PowerShell hash probe was unavailable; Python SHA-256 checks supplied final evidence.
- Initial status field selection returned absent top-level configuration fields;
  deployment metadata confirmed `/frontend`, Dockerfile builder and `/healthz`.

## Delivery and recovery boundary

Existing Railway project `04320f63-ab40-426f-ab35-02fcb365c3b8`, staging environment
`d8e64109-9863-4faa-a45e-f072adb3cfac`, web service
`167269a6-26cb-40f6-b129-b698127c87ee`. Fresh successful web deployment:
`db15b2c1-55d5-47c6-aae8-d1132936716c`; API remains
`0aefad8b-aed6-456e-9e1c-35b637f3272e`. Keep existing source binding/configuration.
The previous successful web deployment is the recovery reference, not a request to
redeploy automatically. Uncommitted source still needs a separately authorized Git
checkpoint; a future GitHub deployment can supersede an uploaded local candidate.

After explicit approval, recheck manifest and current deployment, upload only the
prepared source to the existing web service, wait for SUCCESS and verify HTTP health,
SPA/API routing, exact assets and cache headers. Then check authenticated Admin names
and bindings plus Employee bowl dialog and preserved progress. Stop and report if the
build, health or these checks fail. Any recovery deployment requires its own authority.

Only after delivery: verify eight duplicate pairs by exact item binding in v5, remove
the redundant draft occurrences while retaining variants, and review the result.
Publication, assessment recovery and progress rollout remain a separate approval gate.
