# HoReCa Frontend

CRA-43 is accepted, Done, and published through `fa30a1f`. Accepted CRA-49 extends that frontend
with Menu administration, explicit JSON review/publication, and an Active Employee published-menu
reference; CRA-49 and its corrective acceptance tail are fast-forward published through `8028d6e`.
Accepted CRA-54 adds the Admin Training authoring workspace and Active Employee Module/Lesson
reference reader; its nine-checkpoint implementation is published through `d955f6a`.
Accepted CRA-57 adds Admin Assignment and replacement-Version Rollout controls plus an
assignment-aware Employee Learning, Lesson Completion, and Progress experience. Its nine
checkpoints are published through `d4e0184`, with the CRA-58 documentation checkpoint at
`5dc459b`.
The application uses React 19, TypeScript 6,
Vite 8, Tailwind CSS 4, Vitest, Testing Library, and Playwright. The UI is Ukrainian-first,
server-session driven, responsive, keyboard accessible, and reduced-motion aware.

## Local setup

Use Node.js 24 and pnpm 11. From `frontend/`:

```powershell
rtk pnpm install --frozen-lockfile
rtk pnpm dev
```

The development server calls same-origin `/api/v1` routes. Authentication uses the backend's
Secure HttpOnly session cookie; protected mutations add the server-issued CSRF token, and bounded
retryable actions add an idempotency key. Do not store credentials or raw invitation tokens.

## Quality gate

```powershell
rtk pnpm format:check
rtk pnpm lint
rtk pnpm typecheck
rtk pnpm test
rtk pnpm build
rtk pnpm exec playwright install chromium
rtk pnpm test:e2e
```

Playwright starts Vite on `127.0.0.1:4173` and supplies deterministic API route mocks. It does not
replace the accepted real-PostgreSQL backend gate; it proves browser routing, form behavior,
responsive presentation, and the frontend-to-contract request boundary.

## Implemented boundary

- Admin login with server-selected MFA continuation.
- New-account invitation acceptance and Pending Employee state.
- Admin Employees list and invitation creation.
- Pending-only profile setup followed by a separate confirmed Activation request.
- Active Employee home with real profile context and an explicit zero-assignment state.
- Location-scoped Admin Menu Draft editing, JSON preview/review/confirm, readiness, and publication.
- Active Employee published Menu search, section/category filters, locale fallback, and safe item
  detail with components and allergens.
- Location-scoped Admin Training Draft editing, typed lesson blocks, private image upload,
  readiness, conflict recovery, reorder actions, and confirmed atomic publication.
- Active Employee published Training Module/Lesson reading with locale fallback, signed images,
  Menu Item cards, and allowlisted privacy-safe YouTube embeds.
- Admin Employee assignment, revoke, and reassign controls with explicit impact and lineage-aware
  states.
- Admin replacement-Version Rollout preview, preserve/repeat Lesson decisions, stale-conflict
  recovery, and confirmed rollout execution.
- Assignment-aware Employee Learning with current and retained-Version access, explicit Lesson
  Completion, derived Progress, and one truthful next action.
- Loading, empty, error, disabled, and forbidden route states used by this slice.

Practice, Question Bank, Knowledge Check, Final Exam, Results, provider delivery, password reset,
deployment, and production environment configuration remain outside the accepted Slice 4
boundary. CRA-57 notification behavior is limited to safe transactional local jobs; it does not
call an external provider.

Fresh CRA-49 backend/frontend/browser evidence is recorded in
[`../docs/testing/menu-slice-2-acceptance.md`](../docs/testing/menu-slice-2-acceptance.md).
Accepted CRA-54 evidence is recorded in
[`../docs/testing/training-slice-3-acceptance.md`](../docs/testing/training-slice-3-acceptance.md).
Accepted CRA-57 evidence records 35 Vitest tests and 12 Playwright executions across the approved
desktop, tablet, and mobile projects in
[`../docs/testing/training-assignment-slice-4-acceptance.md`](../docs/testing/training-assignment-slice-4-acceptance.md).
