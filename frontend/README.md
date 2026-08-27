# HoReCa Frontend

CRA-43 implements the first bounded frontend slice against the accepted backend contracts. It uses
React 19, TypeScript 6, Vite 8, Tailwind CSS 4, Vitest, Testing Library, and Playwright. The UI is
Ukrainian-first, server-session driven, responsive, keyboard accessible, and reduced-motion aware.

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
- Loading, empty, error, disabled, and forbidden route states used by this slice.

Training content, assignments, progress, practice, exams, password reset, provider integrations,
deployment, and production environment configuration remain outside CRA-43.
