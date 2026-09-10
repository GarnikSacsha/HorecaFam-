# CRA-131 public start page — local editorial candidate

Date: 2026-09-09. Issue: [CRA-131](https://linear.app/craftspacee/issue/CRA-131).
Base: `main`, `fafec73ad7f3438e1b545acea7cde3018b7f2fbf`. Uncommitted candidate;
unrelated pre-existing changes preserved. No Git index, commit, push or deployment action.

## Sources and outcome

Read the global Denys Agent Harness in its separate repository, local `.harness/START-HERE.md`
and implementation/quality/security/testing/Git instructions, Linear START HERE
(`cde401714974`), current visual direction (`ee0ace76276f`), demo checkpoint (`54d129164060`),
CRA-19 and its comments, and related CRA-16/17 context. CRA-131 bounds implementation of
Denys's selected first editorial option; CRA-19 alone was design scope.

The public `/` formerly depended on session discovery and showed a session failure with an
unavailable API. It now renders an introductory page during pending, anonymous and failed
session discovery. Authenticated visitors retain the existing role destination. Protected
routes, backend contracts and the postactivation Welcome behavior are unchanged.

The candidate includes the official logo, blue/white editorial typography, existing team and
food photography, real resources/audience anchors, informational learning blocks, and a single
login action repeated at the end. Login has matching branding and a link back to the public page.
There is no registration, carousel, generated photography or new dependency.

## Ordered commit map and exact selective paths

Commit authorization has not been given; these remain unstaged boundaries, in order:

1. `feat(frontend): add public Bacara editorial entry`: `frontend/src/public/`,
   `frontend/src/assets/bacara/`, `frontend/src/app/App.tsx`,
   `frontend/src/app/App.test.tsx`, `frontend/src/auth/LoginPage.tsx`, `frontend/index.html`.
   Verify focused App/session/auth tests, formatting, lint, types and build.
2. `test(frontend): verify responsive public entry`: `frontend/e2e/public-start.spec.ts`,
   `frontend/README.md`, `docs/testing/public-start-editorial.md`.
   Verify full browser matrix, keyboard/reduced-motion behavior, visual review and full Vitest.

Do not stage `Photos/`, test output or unrelated dirty paths.

## Asset provenance and limitations

The four JPEG assets are byte-for-byte copies; source `Photos/` files were not edited.

| Bundled file under `frontend/src/assets/bacara/` | Source under `Photos/` |
| --- | --- |
| `team.jpg` | `bacara-instagram-Dbv74IbDvIt-frame-1.jpg` |
| `food.jpg` | `bacara-instagram-DRfEEUyDH8e-frame-1.jpg` |
| `bakery.jpg` | `bacara-instagram-DN-dH8wDWq8-frame-1.jpg` |
| `together.jpg` | `bacara-instagram-DQ2GIjtDrS6-frame-1.jpg` |

`bacara-logo.svg` is the unmodified official header asset observed at
<https://bacara.com.ua/wp-content/uploads/2025/10/Logo-4.svg>, bundled locally.
The page does not hotlink assets. Existing photos retain Instagram overlays and their limited
resolution; clean original photography is a later replacement, not a claim of production-ready
assets. CSS frames crop presentation only; the source images remain intact.

The palette follows the accepted blue `#011ED3` with white and `#F7F7F7`. Klaster Sans is
declared with Arial/Helvetica fallback. No licensed font binaries were supplied or downloaded;
the current visual review uses the fallback. Final copy and visual acceptance remain with Denys.

## Verification

Commands were run from `frontend/` using the repository toolchain.

- RED: `rtk pnpm test src/app/App.test.tsx` before implementation: 1 passed, 4 failed,
  0 skipped. Failures were the missing public story/navigation; role routing passed.
- Focused GREEN: App, SessionGate and AuthFlow tests: 10 passed, 0 failed, 0 skipped.
- `rtk pnpm test`: 76 passed, 0 failed, 0 skipped across 21 files.
- `rtk pnpm test:e2e`: 51 passed, 0 failed, 0 skipped; 1440×1000, 768×1024 and 375×812.
  Includes all 42 existing browser executions and nine new public-entry executions.
- `rtk pnpm build`: passed, including TypeScript compilation and Vite production build.
- `rtk pnpm format:check`, `rtk pnpm lint`, `rtk pnpm typecheck` and
  `rtk git diff --check`: passed. Four asset copies were verified byte-identical;
  the SVG element inventory contains only svg/group/mask/path elements.
- The first browser run had three failures caused by a new test using an English label for the
  existing Ukrainian email input. Correcting the locator yielded the complete passing run.
  Initial type/lint findings in new test code were corrected without weakening assertions.
- Desktop page reviewed in the live browser; compact and mobile full-page screenshots produced
  by Playwright were inspected. Photos load, layout has no horizontal overflow, anchors reach
  their sections, keyboard skip link focuses main content, and reduced motion disables smooth
  scrolling. This is focused accessibility evidence, not a complete conformance audit.

Browser tests mock the API. No real backend authentication, PostgreSQL, container or deployed
provider acceptance is claimed. Local preview: `rtk pnpm dev`, <http://127.0.0.1:5173/>.
CRA-131 remains In Progress pending visual acceptance.
