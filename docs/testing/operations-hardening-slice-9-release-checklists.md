# CRA-77 Release, Restore and Rollback Checklists

## Purpose and boundary

This file separates the completed local CRA-77 acceptance from external release-readiness work.
Only checked items have current evidence. Unchecked items require their own bounded Linear issue,
explicit approval and provider or target-environment evidence. This checklist does not authorize a
push, deployment, provider call, non-test bootstrap, data migration, restore or production change.

## Completed local acceptance

- [x] The authorized thirteen-checkpoint range is `974feeb..ef74be4`.
- [x] Independent security, isolation and transaction review found no High or Critical defect.
- [x] Backend format, lint and strict typing are green.
- [x] The full dedicated-PostgreSQL suite reports 530 passed, 0 failed and 0 skipped.
- [x] Overall statement/branch coverage is 86%; the predeclared nine-file critical set is 81%.
- [x] Alembic upgrade, current-head and metadata no-drift checks are green at `0018_job_runtime`.
- [x] Frontend format, lint, typing and production build are green.
- [x] Vitest reports 72 passed; Playwright reports 42 passed across the approved viewports.
- [x] Keyboard, browser accessibility-tree, contrast and reduced-motion review is recorded.
- [x] Synthetic invitation-to-passing-result and dry-run/idempotent bootstrap paths are covered.
- [x] No provider, production, non-test bootstrap, backup/restore or real-venue action was performed.

## Staging release checklist

- [ ] Record a bounded staging issue and explicit deployment/provider authorization.
- [ ] Confirm isolated staging secrets, database, origin, cookie, CSRF and operator configuration.
- [ ] Take and identify a restorable pre-release database backup.
- [ ] Deploy the accepted API, frontend, worker and maintenance scheduler from one immutable ref.
- [ ] Run migrations to `0018_job_runtime` and verify one current head with no drift.
- [ ] Verify health, structured request/job correlation and redaction in the configured sink.
- [ ] Exercise Admin password login, MFA enrollment/recovery and session revocation.
- [ ] Exercise invitation delivery with an approved staging recipient and provider.
- [ ] Complete invitation through one passing Final result and verify Admin audit visibility.
- [ ] Run the separately accepted load profile and attach measured latency/error/lease results.
- [ ] Record staging acceptance, failures and rollback decision in Linear.

## Backup and isolated restore drill

- [ ] Confirm provider retention meets the accepted policy and names the responsible operator.
- [ ] Create a fresh labeled backup before the drill without exposing credentials or customer data.
- [ ] Restore into an isolated, access-restricted database; never overwrite staging or production.
- [ ] Verify Alembic head, schema constraints and representative row counts after restore.
- [ ] Verify Disabled memberships remain disabled and all prior Sessions remain non-authoritative.
- [ ] Verify immutable assessment/job attempt history and tenant-scoped audit history are intact.
- [ ] Run a read-only smoke through authentication, Employee state, Results, audit and operator jobs.
- [ ] Record recovery-point and recovery-time evidence, discrepancies and corrective actions.
- [ ] Destroy the isolated restore only under a separately approved, exact-target cleanup procedure.

## Production release and rollback checklist

- [ ] Record explicit production, provider, migration and bootstrap authorization.
- [ ] Pin the accepted immutable ref and verify its artifact provenance.
- [ ] Confirm current backup, restore evidence, maintenance window and responsible rollback owner.
- [ ] Verify production secrets and allowlists without printing them to logs or task output.
- [ ] Apply migrations once; verify `0018_job_runtime` and no metadata drift.
- [ ] Deploy API, frontend, worker and scheduler; verify health and lease progression.
- [ ] Run approved non-destructive auth, audit, operator and synthetic smoke checks.
- [ ] Observe error rate, latency, job failures, retry depth and sensitive-field redaction.
- [ ] Trigger rollback on the accepted threshold; otherwise record the successful observation window.
- [ ] Prefer an approved forward fix when migrated data makes binary rollback unsafe.
- [ ] If rollback is required, use the pinned prior artifact and the accepted database recovery plan.
- [ ] Record final state, timestamps, evidence links and follow-up issues in Linear.

## Physical accessibility and venue UAT

- [ ] Complete NVDA or JAWS keyboard-only authentication and recovery on a supported Windows setup.
- [ ] Complete VoiceOver or TalkBack smoke on one supported mobile device.
- [ ] Validate zoom/reflow, focus visibility and reduced motion on physical target browsers.
- [ ] Run Admin and Employee venue workflows on the actual network/device profile.
- [ ] Validate real Bacara content, locale, roles and operational ownership with venue stakeholders.
- [ ] Record defects, accepted limitations and final pilot sign-off in the bounded release issue.
