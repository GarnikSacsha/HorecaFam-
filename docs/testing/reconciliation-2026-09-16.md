# HoReCa reconciliation — 2026-09-16

## Authority and boundary

Denys approved repository/Linear synchronization and the proposed selective local commits
after the read-only product audit. CRA-122 owns documentation reconciliation; CRA-233 and
CRA-234 retain their separate existing implementation scopes. This work introduces no new
product behavior and does not authorize push, PR, deployment, provider sends, migrations,
content import/publication or non-test data changes. Issue statuses remain unchanged.

Documentation uses the documentation-only TDD exception: inspect sources, links, exact diff,
safe content and readback. Existing implementation RED evidence remains in the CRA-233/234
reports; this task reruns GREEN checks and does not reconstruct or claim a new RED.

## Initial source and runtime evidence

- Repository root is the existing HoReCa checkout; branch `main`, initial HEAD `eae1af0`.
- Direct `git ls-remote origin refs/heads/main` returned
  `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`: local ahead 26, behind 0. The sandbox network
  attempt failed before connection; the approved read-only retry succeeded. No pull/fetch/push.
- Global Harness remains pinned at `3eaa9586b4e09e70399c2600aa1808b18449a15d`.
  Its operating contract and relevant routed guidance were read; no upstream update is needed.
- September 15 delivery evidence identifies API `e3297673-0ae5-428a-b94a-085c0d80a2fc`,
  web `7875de0b-c9b8-4f09-b812-14f72874e560` and worker
  `7eba759c-d82c-46f8-8067-c4d77d7a1d6b`. This is recorded provider evidence, not a new
  provider inventory. Invitation delivery completed on attempt 1 and Resend reported Delivered.
- The sealed CRA-233 packet has 384 files. September 16 read-only verification found zero
  hash mismatches and extra files; ZIP SHA-256 is
  `a2819699aa18e62014b96dbb934e7b022e53e1d52c9f0ce68948be3c735ed0e5`.
  CRA-234's new body-limit module is absent from that packet. Local fixes are not deployed.
- Authenticated staging UI read on September 16: one active Employee, zero awaiting activation,
  zero assignments/certifications; Menu Draft v1 has zero items and `MENU_EMPTY`; Training
  Draft v1 has zero lessons, no selected Waiter audience and no Published Menu dependency;
  question generation is disabled because Published Menu/Training sources are absent.
  No records were edited and the browser returned to Dashboard. This confirms active access,
  not completion of the learning journey or full staging acceptance.

## Ordered selective commit map

Each implementation checkpoint must pass its mapped checks and exact diff review before commit.
No accepted checkpoint is amended, squashed or otherwise rewritten.

1. **CRA-233 backend — `feat(invitations): list organization invitations safely`.**
   Paths: `backend/app/api/routes/invitations.py`, `backend/app/schemas/invitations.py`,
   `backend/app/services/invitations.py`, `backend/tests/api/test_invitations_list.py`.
   Gate: list plus existing resend/revoke PostgreSQL tests; Ruff and strict mypy.
2. **CRA-233 UI — `feat(admin): expose invitation list and explicit resend`.**
   Paths: `frontend/src/api/contracts.ts`, `frontend/src/admin/AdminEmployeesPage.tsx`,
   `frontend/src/admin/AdminInvitationsPanel.tsx`, `frontend/src/admin/AdminInvitations.test.tsx`,
   `frontend/src/admin/AdminFlow.test.tsx`, `frontend/e2e/admin-invitations.spec.ts`.
   Gate: full same-session Vitest, focused three-viewport Playwright, formatting/lint/types/build.
3. **CRA-234 recovery — `fix(auth): preserve recovery during anonymous budget saturation`.**
   Paths: `backend/app/services/password_recovery.py`,
   `backend/tests/api/test_password_recovery.py`, `backend/tests/api/test_rate_limit_capacity.py`.
   Gate: recovery/capacity plus adjacent recovery worker and database checks; Ruff/mypy; fresh
   separate review of lock, token, throttle and response-parity boundaries.
4. **CRA-234 body limit — `fix(api): bound request bytes before parsing`.**
   Paths: `backend/app/core/request_body.py`, `backend/app/main.py`,
   `backend/tests/api/test_request_body_limit.py`.
   Gate: body/health/errors and menu-import compatibility tests; Ruff/mypy; fresh separate review
   of middleware order, actual-byte counting, replay and error envelope.
5. **Feature evidence — `docs: reconcile invitation and security correction evidence`.**
   Paths: `docs/testing/admin-invitation-resend.md`, `docs/testing/security-fixes-cra-234.md`.
   Gate: exact checkpoint/test counts, preserved dated RED/GREEN evidence, links and safe diff.
6. **CRA-122 documentation — `docs: synchronize staging and product readiness checkpoint`.**
   Paths: `.harness/UPSTREAM.md`, `README.md`, `CONTEXT.md`, `STATUS.md`, `backend/README.md`,
   `docs/architecture/README.md`, `docs/testing/README.md`, `docs/testing/account-provisioning.md`,
   `docs/testing/caddy-delivery-cra-123.md`, `docs/testing/coverage-closure-plan.md`,
   `docs/testing/demo-candidate-2026-09-10.md`, `docs/testing/public-start-editorial.md`,
   `docs/testing/reconciliation-2026-09-16.md`, `docs/deployment/staging-cra-122.md`,
   `docs/deployment/staging-acceptance-cra-122.md`,
   `docs/deployment/cra-122-source-build-preparation.md`,
   `docs/deployment/staging-preflight-2026-09-12.md`,
   `docs/deployment/cra-122-build-settings.draft.json`,
   `docs/deployment/cra-122-source-binding.draft.json`, `docs/deployment/staging-cors-proposal.json`.
   Existing preparation JSON is retained as historical input, not retargeted or applied.
   Gate: review accumulated documentation, validate relative links/JSON, scan safe content,
   verify Git/packet inventory and Linear readback. No global Harness policy change.

Excluded: `Photos/`, `outputs/`, secrets, caches, local helpers and all other worktrees.
The pre-existing metadata-only `question_generation.py` mark is not part of any checkpoint.

## Verification and checkpoint ledger

Source commits: `80c0996`, `58ad81f`, `3b3c79a`, `0f767a6`; feature evidence: `c00009f`.
The final documentation commit follows these five checkpoints and includes the mapped 20 paths.

| Fresh verification | Result |
| --- | --- |
| Invitation list/resend PostgreSQL | 21 passed, 0 failed, 0 skipped |
| Recovery/capacity and adjacent database/worker tests | 36 passed, 0 failed, 0 skipped |
| Body/health/errors/menu-import tests | 41 passed, 0 failed, 0 skipped |
| Full same-session Vitest | 112 passed in 26 files, 0 failed, 0 skipped |
| Focused invitation Playwright | 3 passed, 0 failed, 0 skipped; mocked APIs |
| Backend static checks | Ruff format/check passed; strict mypy passed, 239 source files |
| Frontend static/build checks | Formatting, lint, types and build passed; existing bundle-size warning |

The initial sandbox frontend startup failure ran no tests; the authorized retry passed.
Earlier overlapping test selections are not added to these totals. No full backend coverage,
full Playwright regression or fresh provider deployment verification is claimed.

Linear synchronization uses a brief progress/navigation update. Automatic approval review
rejected the detailed external update because it contained internal staging/deployment and test
metadata. The reduced update omits those details and was saved and read back in START HERE, the demo
roadmap, Stage 2, the project and CRA-122/233/234/148. All four issue states remain In Progress.
Technical facts remain in this repository. The initial CRA-122 authorization record was already saved.
Detailed remote checkpoint parity is therefore not claimed; read this ledger for exact evidence.
Issue states remain unchanged. No push, deployment or production-data write occurred.

Final documentation validation: 20 mapped files, three JSON files parsed, 253 relative links
resolved with zero missing targets; targeted credential-pattern scan found no matches.
The exact staged inventory and whitespace check are required before the final commit.

## Next product boundary

Use the existing prepared menu import and first four lessons, subject to explicit content-write
authorization. Review/publish Menu, select the Waiter audience, bind the exact Published Menu,
author/publish Training, review/publish generated questions, prove 5/10/20-question readiness,
assign the existing active Employee and exercise Admin/Employee Results. Do not recreate users,
repeat activation, resend the invitation or repeat completed migrations from historical lists.
CRA-234 delivery, GitHub publication and the full staging/pilot gates remain separate decisions.
