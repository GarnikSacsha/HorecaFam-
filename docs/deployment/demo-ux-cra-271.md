# CRA-271 demo UX delivery — 2026-09-17

Denys explicitly authorized deployment after the six CRA-271 commits were pushed to main
through `9d68d9d`. This delivery preserves deployed CRA-237/238/240 fixes and excludes unrelated
CRA-234 changes. It is an isolated source upload, not a deployment of raw Git HEAD or the dirty
worktree. Existing question publication and historical attempts are unchanged.

## Candidate and verification

The sealed CRA-240 backend and CRA-238 frontend archives were hash-verified against their
recorded manifests. The `fde81b4^..9d68d9d` backend/frontend patch was applied on top. The CSS
addition was appended explicitly because the deployed file already contains earlier uncommitted
readiness styles. The candidate has 397 files and 42 changed paths against those two bases.

Local excluded packet: `outputs/cra-271-candidate-2026-09-17/source.zip`.
SHA-256: `6aeb978e3f1678ac7b11b70f2060c323c4264f5fc651e4a3ef09bb750478759a`.
The source directory contains no environment files, credentials, node_modules, runtime output,
Git metadata or protected Photos. Validation runs in a separate copy.

Exact candidate verification: 32 backend tests passed, 0 failed/skipped, covering generation,
review, menu history, existing readiness correction and menu Admin APIs. Four frontend files:
22 tests passed, 0 failed/skipped. TypeScript and Vite production build passed. Vite retains a
non-blocking large-chunk warning. Candidate JS is `index-B5fENSqR.js`, CSS `index-BiyR8wr3.css`.
An initial pnpm invocation attempted dependency reconciliation and stopped without installation;
the same package-script tools then ran directly against the existing installed dependencies.
Existing broader implementation evidence remains in the [testing report](../testing/demo-ux-followup-2026-09-17.md).

## Migration

The existing staging migration-runner was temporarily configured to run a bounded release
helper, using its existing private migration credentials. Its normal command was read from
current settings and restored afterward to `python -m alembic upgrade head`. No variables,
database proxy, schedules, replicas or credentials changed. CLI SSH was unavailable; delivery
used normal Railway source uploads and GraphQL settings, with no browser-console workaround.

Migration deployment `33b88012-bb7b-487b-923d-8e6ce053ee37` reached SUCCESS. Its safe control
events verified the expected database/migrator identity and schema head 0019 before running
Alembic to `0020_menu_change_history`. The new table has 12 columns. Only its existing runtime
role received SELECT/INSERT/UPDATE/DELETE; checks denied excess table privileges, grant options,
schema CREATE and migration-table SELECT. No rows were backfilled or existing application data
updated. The helper exists only in the separate migration upload, not API/web source.

## Rollout

API deployment `adffd5f0-2675-4ca7-916a-9b3f1d8627de` and web deployment
`82941686-422a-4f05-a09d-c03ce43e26e5` both reached SUCCESS. Eight HTTP checks passed, zero
failed/skipped: web health, API health, public entry, login, unknown API/asset 404s and the exact
new JS/CSS assets. HTML no-store and immutable asset cache headers were verified.

Authenticated live browser checks confirmed the new empty Menu history view without errors;
Admin Results retained the existing 95% (19/20) certification, showed Practice 70%, date and
one completed exam, and loaded the completed-answer review with the single mistake by default.
Employee Home displayed certification/date and a result link instead of prompting another exam.
Reopening Employee Final Exam displayed the persisted 95% summary, 19/20 correct, one error,
zero critical errors and the existing attempt date/history.
No synthetic menu edit or new attempt was created for verification.

Previous recoverable API deployment is
`c346bfcb-8526-4c56-b399-0daed5154c75`, previous web is
`28e00b65-1409-407f-98bb-cacfe43e845b`. The additive table is compatible with the old application;
do not drop new history as an application rollback step.

## Boundaries

No worker/cron deployment, content write, question-bank regeneration/publication, email send,
additional Git commit/push or PR. Existing published questions keep their option counts and
selection metadata; the new generation format requires a separately reviewed publication.
Menu history begins with new manual Draft item edits; imports/publication/backfill and email
digests remain outside this release.
