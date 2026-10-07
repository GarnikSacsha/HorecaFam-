# CRA-288: initial training content

Stage 3 adds an explicit Admin preview/import to the existing Training draft editor.
It creates three position-scoped modules: Runner (6 lessons/15 scenarios), Bartender
(6 lessons/20 scenarios), and shared Service Standards (11 lessons/10 scenarios).
The stable catalog is Ukrainian, generic and versioned. It contains no venue recipes,
invented company policy, numerical drink recipes or operational opening/closing checklist.

The administrator can map the existing Waiter position, including a nonstandard role code.
Runner and Bartender reuse organization OperationalRoles. Import appends root audiences and
new modules without changing existing Menu/Waiter lessons or audiences. It does not assign
employees or publish Training. Replays, including another click and a cloned complete pack,
do not duplicate content; partial packs are rejected for manual review.

Preview exposes full educational material and scenario rationale to an authenticated Admin.
Import requires explicit acknowledgement, MFA through the existing Admin dependency, CSRF,
idempotency and the draft revision. Confirmed generic sources become immutable pinned source
versions. Questions are generated only after Training publication and remain `needs_review`
until individually approved in the existing question bank. An unsuccessful import rolls back
the operation; no partial roles/content are committed.

TDD: the first API test failed with the missing endpoint (404). The frontend test failed on
the missing preview action. Both became green. API checks cover all 23 lessons/45 sources,
valid content payloads, preservation of the original Menu module, repeat safety, audience
separation, revision/CSRF/scope/acknowledgement denials, conflicting role mapping with rollback,
publication readiness and generation of 45 unapproved candidates.

The affected backend run passed **48 tests, 0 failed, 0 skipped** (91.12 seconds), including
content import, publication, position access and standard-source regressions.
The Training editor suite passed all 17 tests; TypeScript and ESLint passed. Ruff and strict
mypy passed (277 source files). No dependencies or schema changes in this content boundary.
Runtime files are excluded from Git. Full acceptance remains the final CRA-288 gate.
