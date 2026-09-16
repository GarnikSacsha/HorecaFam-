# CRA-233 — Admin invitation list and resend

## Current reconciliation — 2026-09-16

Denys authorized the ordered local commits: backend `80c0996`, Admin UI `58ad81f`.
This report is the separate evidence boundary. The September 15 uncommitted/pending-acceptance
wording below is historical: authenticated Admin UI now shows one active Employee and zero
awaiting activation. No new send or user change occurred during this reconciliation.

Fresh list/resend PostgreSQL selection: **21 passed, 0 failed, 0 skipped** (64.82 s).
Same-session full Vitest: **112 passed in 26 files, 0 failed, 0 skipped**; focused three-viewport
Playwright: **3 passed, 0 failed, 0 skipped** (9.1 s; mocked APIs). Backend Ruff format/check
and strict mypy pass; frontend formatting, lint, types and build pass. The existing 501.74 kB
bundle warning remains non-failing. Initial sandbox Vitest startup failed before tests;
the authorized retry passed. No full backend coverage or full Playwright rerun.

The 384-file delivered packet was rehashed: zero mismatches/extras; recorded ZIP hash unchanged.
CRA-234 is a separate local correction and is not in this deployment packet. Current source,
Linear routing and remaining gates: [reconciliation ledger](reconciliation-2026-09-16.md).

## Historical September 15 implementation and delivery evidence


## Authorized staging delivery — 2026-09-15

Denys explicitly approved API/web deployment and the controlled send after reviewing the sealed
candidate. All 384 source files and archive hash were reverified before upload.

- API `e3297673-0ae5-428a-b94a-085c0d80a2fc`: SUCCESS, health passed.
- Web `7875de0b-c9b8-4f09-b812-14f72874e560`: SUCCESS, `/healthz` passed. Build produced
  `index-dtqM3Ti3.js`, matching the candidate build filename.
- Worker remains `7eba759c-d82c-46f8-8067-c4d77d7a1d6b`; no additional worker rollout.
- Five final HTTP checks passed, zero failed/skipped: web health, API health, Admin page,
  anonymous invitation GET denied with 401, missing `/assets/` file returns 404. The first smoke
  used `/missing-asset.js` outside the assets namespace and incorrectly expected 404; its SPA
  fallback 200 was a probe expectation error. Corrected probe uses `/assets/missing-asset.js`.
- Authenticated Admin list displayed the existing expired invitation. One explicit resend was
  performed, without creating a second invitation or changing the recipient. The UI reports
  pending/awaiting acceptance, expiry September 18 at 18:25:33 Europe/Kyiv.
- New job `6c2ce713-bbfe-4218-a34b-22bcb5c1ac50`: **completed on attempt 1/5**, no error;
  delivery `resend: accepted`. Worker logs independently show one claimed and one completed job.
- Resend email `1186d489-29d4-4cc2-b58c-25298d6f27d6`: **Delivered**, subject
  `Вас запрошено до Bacara Academy`. One email row appeared after the previously empty list.
  Recipient address and invitation token are deliberately omitted from evidence.

Delivered is provider confirmation, not proof the recipient opened the mailbox or accepted the
invitation. Acceptance, profile setup and explicit activation remain the next user journey.
The old failed Job is retained as history and was not manually retried or deleted.
No Git commit/push, migration, new credentials, cron launch or unrelated settings change.
The implementation remains uncommitted locally; deployed recovery is the sealed candidate.

The following preparation sections describe the earlier local-only checkpoint.

## Outcome

Admin Employees now lists existing invitations and offers an explicit resend action for pending
and expired invitations. Accepted/revoked invitations have no resend button. The existing resend
service rotates the token, resets expiry to three days and queues an email; the UI reports queued,
not delivered. New invitation creation refreshes the list.

Source: [CRA-233](https://linear.app/craftspacee/issue/CRA-233/expose-invitation-list-and-resend-action-in-admin-employees),
the FINAL CRA-12 invitation clarification and existing resend implementation. Denys authorized
this bounded implementation after the worker configuration/deployment check on September 15.

## Contract impact

Added `GET /api/v1/organizations/{organization_id}/invitations` for Organization Admins with MFA.
It reuses `require_organization_admin`; inaccessible organizations are masked with 404 and an
Admin lacking MFA receives 403. Anonymous reads receive 401.

Response: `items: InvitationResponse[]`, `next_cursor: UUID | null`. Default limit 50, valid range
1–100; ascending immutable UUID cursor. This ordering is stable across resend and is not
chronological. Every query is organization-scoped. Existing safe invitation fields are reused;
tokens, hashes and job payloads are absent. No migration, dependency or resend lifecycle change.

The UI uses the existing CSRF-protected POST resend and a per-invitation idempotency key. Buttons
are disabled while reading/sending and a synchronous lock prevents concurrent submits. Uncertain
network/server failures retain the key for retry within the mounted panel. A full browser reload
does not persist this local retry key. Read failures remain isolated from the Employee list.

## Changed files / ordered commit boundaries

At the September 15 implementation checkpoint, no Git staging or commits had been performed.

1. Backend read contract: `backend/app/api/routes/invitations.py`,
   `backend/app/schemas/invitations.py`, `backend/app/services/invitations.py`,
   `backend/tests/api/test_invitations_list.py`.
2. Admin UI: `frontend/src/api/contracts.ts`, `frontend/src/admin/AdminEmployeesPage.tsx`,
   `frontend/src/admin/AdminInvitationsPanel.tsx`, `frontend/src/admin/AdminInvitations.test.tsx`,
   `frontend/src/admin/AdminFlow.test.tsx`, `frontend/e2e/admin-invitations.spec.ts`.
3. This evidence report. Selective staging only if explicitly authorized.

## Verification — 2026-09-15

- Backend RED: four new cases failed because GET was absent (405 / missing items); 17 existing
  resend cases passed. During GREEN, two expectations were corrected to the established 404
  resource-masking contract instead of changing authorization behavior.
- Final PostgreSQL suite: **21 passed, 0 failed, 0 skipped**, 60.59 seconds. Tests cover expiry
  projection, exact safe response fields, populated tenant isolation, cursor pagination, bounds,
  anonymous/non-Admin/MFA denial plus the 17 existing resend/revoke cases.
- UI RED: four new cases failed for missing invitation UI. Final Vitest Admin invitation and
  Employee flows: **10 passed, 0 failed, 0 skipped**. Existing mocks were extended for the new GET;
  POST verification now selects the write instead of assuming it is the last request.
- Playwright: **3 passed, 0 failed, 0 skipped**, desktop/compact/mobile. Keyboard resend, CSRF,
  idempotency header, one request, updated status and no horizontal overflow. Mobile screenshot
  visually inspected. API is mocked; no real provider send.
- Ruff check/format, strict mypy (four files), ESLint (six frontend/test files), Prettier,
  TypeScript and Vite build passed. Vite reports a non-failing 501.74 kB main chunk warning.
- Final diff reviewed; unrelated dirty documents, Photos and runtime files remain unstaged.
  Full backend coverage/full repository regression were not rerun.

## Prepared delivery boundary

Isolated candidate: `outputs/cra-233-candidate-2026-09-15/source`, 384 files. It preserves the
previous deployed CRA-202 packet (including CRA-172 recovery) and overlays only the ten mapped
backend/frontend files above. No credentials, caches, Photos or unrelated files are included.

ZIP SHA-256: `a2819699aa18e62014b96dbb934e7b022e53e1d52c9f0ce68948be3c735ed0e5`.
Manifest is adjacent to the source. The mutable repository root is not the upload target.

Next execution: separately authorize deployment of this packet to existing staging API, then web;
no migration or worker/cron redeploy. Verify deployment IDs and authenticated Admin list; resend
the already-selected expired invitation through the new UI and verify job/provider delivery.
Owner mailbox receipt and invitation acceptance remain distinct checks. No live send or deployment
occurred during CRA-233 implementation. Worker configuration remains the preceding successful
September 15 deployment, not evidence of mail delivery.
