# CRA-151 — organization Admin Dashboard

Denys requires Dashboard before the demo. This implements the existing FINAL API section 11
as a lightweight aggregate endpoint and the Admin landing page `/admin/dashboard`.
The existing Employees, Results and Attention pages remain drill-down destinations.

## Count semantics

`GET /organizations/{organization_id}/dashboard?location_id=<optional UUID>` requires active
organization-admin access and MFA. A foreign location returns 404. Every aggregate is scoped
to the authorized organization and, when selected, the Employee's current profile location.

- Employees: all profiles by membership status; paused is a subset of active, not a fourth
  mutually exclusive membership status.
- Training: non-revoked assignments belonging to active memberships, including paused people,
  counted by assigned/in-progress/completed status. Units are assignments, not people.
- Final Exam: distinct active employees per category. Certification follows an existing passed
  menu Final Exam for the stable Training of a current assignment; later failures do not erase it.
  Needs-exam means a completed current assignment without that certification, not a readiness
  guarantee. Multiple Training assignments can make categories overlap.
- Retakes: distinct active employees with active requirements. Overdue requires a non-frozen
  clock, active participation and `due_at <= now`. There is no invented general training deadline.
- Attention: unresolved open/acknowledged cases; critical counts the critical-allergen subset.
  Resolved cases are excluded. Activity status does not remove unresolved operational cases.

The service executes five aggregate queries, plus one location validation query when filtered.
It does not fetch per-employee histories or mutate domain state. Normal session last-seen
handling remains in the existing authorization dependency. No schema migration or dependency.

## Ordered commit boundaries — not authorized

1. Backend: `app/services/dashboard.py`, `app/schemas/dashboard.py`, `app/api/routes/dashboard.py`,
   router registration and `tests/api/test_dashboard.py` under `backend/`.
2. Frontend: `src/admin/AdminDashboardPage.tsx`, its test and CSS, `src/api/contracts.ts`,
   Dashboard route/navigation/default destination in App/AdminShell/SessionGate, corresponding
   App/SessionGate routing assertions, `e2e/admin-dashboard.spec.ts` and the specific
   employee-profile/vertical-slice routing and exact logout-selector adjustments.
3. This report, STATUS/CONTEXT and Linear current navigation. Preserve unrelated pre-existing
   App and documentation hunks; no index change, commit, push or deployment is authorized.

## Verification — 2026-09-09

Backend RED: missing endpoint returned 404 instead of 200. GREEN and adjacent access/read
tests: **24 passed, 0 failed, 0 skipped** in 184.40s. Command from `backend/` after the guarded
test-environment load in `.harness/TESTING.md`:

```text
rtk ..\.venv\Scripts\python.exe -m pytest tests/api/test_dashboard.py tests/api/test_employee_reads.py tests/api/test_auth_mfa_rbac.py tests/api/test_employee_security.py -q --tb=short -p no:cacheprovider
```

The five Dashboard cases cover empty/populated counts, foreign organization/location, real
Employee denial, missing MFA/anonymous access, non-revoked assignments, duplicate retakes,
paused/frozen deadlines, resolved Attention and durable certification after later failure.
Initial final-assessment fixture configuration was corrected to the existing 20-question/70%
contract; production scoring rules were not changed.

Frontend RED: the new route redirected to Employees and produced the wrong page/error. An
isolated RED case failed for that behavior without the initial unrelated mock-shape exceptions.
Focused GREEN: four Dashboard tests plus two logout tests passed. The page shows loading,
empty/error/retry, location filter and drilldowns; requests from an obsolete selection cannot
replace the current view. The result is keyed to organization/location/request, avoiding stale
counts and effect-driven reset renders. Existing styles and responsive Admin navigation are reused.

Desktop and mobile browser screenshots were inspected: readable counts/units, functional
location selector, no horizontal overflow, keyboard-accessible actions. Browser APIs are mocked.
Final shared frontend totals are recorded in STATUS after the final gate. Early browser failures
identified old post-MFA routing assertions and ambiguous substring logout locators; the tests now
assert Dashboard then open Employees and distinguish the two logout actions explicitly.
One simultaneous Vitest/browser run timed out under local contention; rerun with two Vitest
workers preserves all assertions/timeouts rather than weakening the test limits.

## Protected-boundary review and rollout limit

Authorization is enforced before aggregate reads. Both membership/profile tenant predicates and
each assessment/retake/attention organization predicate remain explicit. Parameterized UUID
filters cannot select an arbitrary user's scope. The response contains counts and scope IDs only,
without names, passwords, raw errors, answer keys, score histories or rankings. Passed certification
uses stable Training lineage and the same Final family restriction as the existing certification
read. No mutation endpoint or generic management privilege was added.

This is local evidence, not hosted acceptance or a refreshed full backend coverage report.
CRA-151 remains In Progress pending Denys acceptance. The selected staging `fafec73` predates
these features; a separately accepted/published replacement candidate is required.
