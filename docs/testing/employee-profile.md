# CRA-147 — read-only Employee profile

Date: 2026-09-09. [Issue](https://linear.app/craftspacee/issue/CRA-147).
Local main base: `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`.

## Outcome and contract

The formerly disabled Profile destination now opens `/employee/profile` behind the existing
active-employee gate. The page reads `/api/v1/me/profile`, selects the active session Organization
as Employee Home does, and displays name, Organization, Location, role and active membership.
It offers no profile editing. Missing values are explicit; missing profiles and failed requests
show safe errors. Retry reloads the profile. Existing current-session logout remains available
while loading or after failure and retains its existing CSRF/error behavior.

Sources read: repository/global operating contracts and applicable harness routes; Linear
START HERE, approved Bacara visual direction, CRA-36 own-profile scope, FINAL CRA-12 relevant
profile/read-only/current-session logout sections, and CRA-147. Existing TypeScript contracts,
SessionGate, Pending/Active Home and LogoutButton were inspected. No API/schema/backend change.

## Selective commit boundaries — no commit authorization

1. `feat(frontend): add read-only Employee profile`
   - `frontend/src/employee/EmployeeProfilePage.tsx`
   - `frontend/src/employee/EmployeeProfilePage.test.tsx`
   - `frontend/src/employee/employee-profile.css`
   - `frontend/src/app/App.tsx` — only profile import and protected-route hunks
   - `frontend/src/shells/EmployeeShell.tsx`
   - `frontend/src/shells/Shells.test.tsx`
   Checks: focused profile/navigation tests, format, lint, types and build.
2. `test(frontend): verify Employee profile browser journey`
   - `frontend/e2e/employee-profile.spec.ts`
   - `docs/testing/employee-profile.md`
   Checks: three viewport journeys, full frontend regression and visual review.

App.tsx also contains pre-existing CRA-131 public-entry changes. Do not stage the whole file for
CRA-147 independently: preserve separate hunks or first publish its separately approved predecessor.
All other pre-existing dirty paths, Photos and outputs remain outside this scope. Git index unchanged.

## Verification

Commands ran from frontend with the existing dependencies. No dependency install occurred.

| Check | Result |
| --- | --- |
| `rtk pnpm test src/employee/EmployeeProfilePage.test.tsx` before implementation | RED: 0 passed, 7 failed, 0 skipped; absent route redirected to Home/public root |
| Profile + Shells focused GREEN | 10 passed, 0 failed, 0 skipped |
| `rtk pnpm test` | 83 passed across 22 files, 0 failed, 0 skipped |
| Final focused profile rerun after test typing cleanup | 7 passed, 0 failed, 0 skipped |
| Focused Playwright profile matrix | 9 passed, 0 failed, 0 skipped |
| Final `rtk pnpm test:e2e` | 60 passed, 0 failed, 0 skipped; 51 existing + 9 new executions |
| `rtk pnpm format:check`, `rtk pnpm lint` | Passed |
| `rtk pnpm typecheck` and final `rtk pnpm build` | Passed; final build includes TypeScript and Vite |
| `rtk git diff --check` | Passed |

Browser viewports: 1440×1000, 768×1024, 375×812. Tests exercise navigation to the profile,
read-only fields, no unexpected mutations, CSRF logout via keyboard, API failure/retry, horizontal
overflow, readable final note after scrolling, and anonymous/Pending/Disabled/Admin redirects.
Desktop and mobile screenshots were visually inspected, including the mobile bottom after scrolling.
Effect cleanup ignores unmounted requests; no raw error content or arbitrary profile selector is shown.

Initial new browser fixture returned success on its second request, so StrictMode's development
effect replay bypassed the expected error (57 passed / 3 failed). It now holds the API unavailable
until explicit retry. A subsequent scroll test used scrollIntoViewIfNeeded, which ignores fixed
navigation overlays (59 passed / 1 failed). The final test scrolls to the page end and polls actual
note/navigation bounds; no production workaround or assertion removal was needed. Initial test
typing/lint issues were corrected. The pnpm exec prettier shim was unavailable; the installed
Prettier entry was run through `rtk proxy node` with only mapped paths.

## Limits and next step

Browser API responses are synthetic route mocks. Backend/PostgreSQL, real authentication/provider
acceptance, Railway and deployment were not exercised. Existing employee shell styling stays intact;
the new profile uses Bacara blue and the documented font fallback. No self-edit, logout-all, role
switching or global redesign was introduced. Review the candidate with Denys; retain In Progress
until acceptance. Commit, push and deployment require separate approval.
