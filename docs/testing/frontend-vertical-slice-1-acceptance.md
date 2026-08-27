# Frontend MVP Vertical Slice 1 — CRA-43 Acceptance Evidence

## Status and boundary

This document records the accepted CRA-43 checkpoint executed on 2026-08-27 with Node.js 24.11.1
and pnpm 11.19.0. CRA-41 and CRA-43 are Done. The six commits `5b7e637..fa30a1f` were fast-forward
published on `origin/main` without history rewriting. PR, merge, deployment, provider calls, and
production configuration remain separate gates and were not executed.

The frontend consumes the existing `/api/v1` contract without backend, schema, migration, or
architecture changes. Route authority comes from the refreshed server session. The browser never
persists the session secret and sends CSRF/idempotency headers only on their accepted mutations.

## Requirement-to-evidence matrix

| CRA-43 boundary                          | Automated evidence                                               | Result |
| ---------------------------------------- | ---------------------------------------------------------------- | ------ |
| Toolchain and production bundle          | TypeScript project references and Vite production build          | Passed |
| API error and protected-request contract | `src/api/client.test.ts` plus Playwright header assertions       | Passed |
| Server-driven route guards               | `src/session/SessionGate.test.tsx` and full browser journey      | Passed |
| Responsive Admin/Employee shells         | component tests plus 1440×1000, 768×1024, and 375×812 projects   | Passed |
| Login and MFA                            | component test plus repeated Admin browser login                 | Passed |
| Invitation and Pending boundary          | component tests plus browser acceptance with no self-activation  | Passed |
| Profile setup and explicit Activation    | component test plus separate PATCH and confirmed POST in browser | Passed |
| Active home truthfulness                 | component test plus zero-assignment browser assertions           | Passed |
| Formatting, lint, and types              | Prettier, ESLint, and TypeScript                                 | Passed |

## RED → GREEN evidence

The browser checkpoint RED was `playwright test` reaching the Vite application and reporting
`No tests found`. After the acceptance scenario was added, the first behavioral run completed the
entire journey but exposed an over-broad negative selector: the disabled shell navigation item
`Практика` matched the test's generic practice-button pattern. The assertion was narrowed to the
contractual rule—disabled navigation is allowed, while no start-practice/start-exam CTA or fake
percentage may exist. No production behavior changed for that test correction.

The first combined final gate also showed that Vitest's default discovery picked up the new
Playwright `e2e/*.spec.ts` file. The tool boundary was corrected explicitly: Vitest owns only
`src/**/*.test.{ts,tsx}`, while Playwright owns `e2e/`. The 13 component/API tests themselves were
green in that diagnostic run.

Final browser result: 3 passed, 0 failed, 0 skipped. One identical business path runs in:

- `admin-desktop`: 1440×1000;
- `admin-compact`: 768×1024;
- `employee-mobile`: 375×812.

The path covers Admin password login and MFA, invitation creation, new-account acceptance,
Pending Employee visibility, logout/login boundaries, Admin profile completion, explicit
Activation confirmation, Active Employee login, and truthful zero-assignment home rendering.

## Frontend gate

Run from `frontend/`:

```powershell
rtk pnpm format:check
rtk pnpm lint
rtk pnpm typecheck
rtk pnpm test
rtk pnpm build
rtk pnpm test:e2e
```

Final accepted results after the documentation audit:

- Vitest: 13 passed, 0 failed, 0 skipped across nine files;
- Playwright: 3 passed, 0 failed, 0 skipped across three viewport projects;
- Prettier, ESLint, TypeScript, and Vite build: passed;
- production bundle: 41 modules, 265.78 kB JavaScript (82.16 kB gzip) and 16.39 kB CSS
  (4.41 kB gzip).

Focused compatibility checks against the unchanged backend also pass:

- `tests/api/test_vertical_slice_acceptance.py`: 2 passed, 0 failed, 0 skipped on the dedicated
  PostgreSQL test database;
- `test_employee_contract_validation_and_openapi_are_exact_and_safe`: 1 passed, 0 failed, 0
  skipped, covering the employee/activation OpenAPI methods and forbidden internal fields.

The full 213-test backend regression was not repeated because CRA-43 changes no backend file,
schema, migration, or dependency; CRA-40's accepted published full gate remains the baseline.

## Limitations and exclusions

- Browser API responses are deterministic route mocks shaped like the accepted backend contract;
  real PostgreSQL behavior remains proved by CRA-40's published backend acceptance gate.
- No fake training, assignment, progress, practice, or exam data is rendered.
- Password reset, MFA enrollment/recovery, broader administration, content workflows, providers,
  analytics, and deployment remain outside CRA-43.
- `Photos/` remains protected CRA-19 material and is untouched, unignored, and unstaged.

## Contract impact

API contract: none. Data model and migrations: none. Backend runtime: none. CRA-43 adds only the
approved frontend runtime, tests, build configuration, and repository documentation.
