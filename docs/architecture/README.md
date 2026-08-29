# Current Architecture

This document describes the verified accepted implementation published through CRA-57 at
`d4e0184`; the CRA-58 documentation checkpoint containing this record follows that range.
Canonical product behavior and contracts remain in Linear.

## Stage 0 runtime path

```text
FastAPI application factory
→ request ID middleware
→ unified exception handlers
→ /api/v1 router
→ GET /health
```

- `backend/app/main.py` creates the application and wires middleware, handlers, and the API router.
- `backend/app/api/router.py` owns the `/api/v1` prefix.
- `backend/app/api/routes/health.py` implements the accepted health boundary.
- `backend/app/core/request_id.py` creates or preserves a valid request ID and correlates safe
  internal-error handling.
- `backend/app/core/errors.py` owns the unified API error envelope.

Exact response shapes, localized messages, error codes, and future endpoints are canonical in
[CRA-12](https://linear.app/craftspacee/issue/CRA-12/define-rest-api-contract-and-pydantic-schemas),
not in this summary.

## Configuration and persistence boundary

```text
required environment configuration
→ async PostgreSQL engine
→ async session factory
→ explicit Alembic migrations
```

- `backend/app/core/config.py` requires an environment and an async PostgreSQL URL.
- `backend/app/db/session.py` creates the SQLAlchemy async engine/session boundary.
- `backend/app/db/safety.py` fails closed unless destructive test work targets `APP_ENV=test` and
  an explicitly test-scoped database.
- `backend/app/db/base.py` owns the shared SQLAlchemy metadata and deterministic naming convention.
- `backend/app/models` defines the seven CRA-28 identity entities, CRA-30 authentication/access
  state, and CRA-32 invitation, idempotency, rate-limit, background-job, and email-delivery state.
- `backend/migrations/env.py` wires that metadata into Alembic.
- `backend/migrations/versions/0001_stage0_empty_schema.py` establishes the base history;
  `0002_identity_persistence.py` creates Stage 1; `0003_auth_security.py` creates Stage 2;
  `0004_invitation_lifecycle.py` and `0005_invitation_email_outbox.py` create Stage 3;
  `0006_menu_source_of_truth.py` and `0007_menu_import_review.py` create the accepted CRA-49 Menu
  schema; `0008_training_content.py` creates the accepted CRA-54 Training content schema;
  `0009_assignment_completion_rollout.py` creates the accepted CRA-57 Assignment, Completion and
  Rollout schema.
- Composite PostgreSQL foreign keys prevent EmployeeProfile role/location references from crossing
  organization boundaries. Membership states are limited to Pending, Active, and Disabled.

The current data design, future models, migration order, and RBAC remain canonical in
[CRA-10](https://linear.app/craftspacee/issue/CRA-10/design-database-schema-and-entity-relationships).

## Stage 2 authentication boundary

```text
password login → ordinary Session or one-time MFA challenge
MFA challenge + TOTP → elevated Session
Session cookie + synchronizer token → protected mutation
Session + scoped access state → deny-by-default RBAC dependency
```

Only `/api/v1/auth/login`, `/api/v1/auth/mfa/verify`, `/api/v1/auth/session`, and
`/api/v1/auth/logout` are production Stage 2 auth routes. Organization/Admin behavior is exposed
only as reusable dependencies and tested through test-only probes; no later-stage product route is
pulled forward.

## Stage 3 invitation boundary

```text
Admin + MFA + CSRF + idempotency key → create/resend invitation
public token body → validate invitation capability
Admin + MFA + CSRF → revoke invitation
business transaction → invitation + audit + background job + email delivery state
worker boundary → reconstruct current raw token only at the delivery adapter call
```

The accepted CRA-32 checkpoint exposes create, validate, resend, and revoke. Tokens are
deterministically derived from server-held ordered HMAC keys and versioned invitation identity;
only hashes and derivation coordinates persist. Delivery state is transactional, but no provider
call or deployed worker is included.

## Stage 4 invitation-acceptance boundary

```text
public invitation token + discriminated account mode
→ locked Invitation and global-email serialization
→ create or authenticate User
→ Pending Membership + placeholder EmployeeProfile
→ accepted Invitation + opaque Session + safe audit in one transaction
→ Secure HttpOnly cookie after commit
```

Accepted CRA-34 adds only `POST /api/v1/invitations/accept`. Invitation email and
Organization remain authoritative; the request cannot redirect identity or tenant ownership.
Concurrent reuse has one winner, all failures roll back, and the issued Session grants only the
existing Pending boundary. Acceptance never activates Membership, assigns Role/Location, or marks
MFA verified. No schema or migration was added.

## Stage 5 Pending/Admin Profile Setup boundary

```text
Admin Session + MFA + Organization scope → safe references and Employee reads
Admin Session + MFA + CSRF + Pending EmployeeProfile → normalized profile replacement
active same-Organization Role/Location + locked transaction → profile + safe audit commit
Employee Session → own read-only operational profiles
```

Accepted CRA-36 exposes Organization summary, Location/OperationalRole references,
cursor-paginated Employee list/detail, own `/me/profile`, and Pending-only Employee PATCH.
EmployeeProfile ID is the public Employee identifier. Tenant filters precede object filters,
cross-Organization probes do not enumerate resources, and completeness is derived from nonblank
names plus active same-Organization Role/Location. No schema/migration, Activation, Assignment,
Training, notification, provider, worker, or frontend behavior is added.

## Stage 6 Explicit Activation boundary

```text
Admin Session + MFA + CSRF + Idempotency-Key
→ scoped EmployeeProfile + Membership locks
→ Pending and completeness/reference revalidation
→ zero-output applicability boundary
→ Active Membership + safe audit + idempotency record in one commit
→ existing employee Session gains Active access without replacement
```

Accepted CRA-38 exposes only
`POST /api/v1/organizations/{organization_id}/employees/{employee_id}/activate`. Employee identity
remains `EmployeeProfile.id`. Same-key replay is side-effect free, key reuse for another target is
rejected, and row locks serialize different-key races. Training participation is derived from the
Active Membership; no Assignment/content/notification record, provider call, job, schema object,
migration, or new Session is created.

CRA-40 adds no runtime architecture. Its Stage 7 boundary is test and evidence only: one complete
real-HTTP/PostgreSQL chain now proves Admin login/MFA through invitation delivery, acceptance,
Pending profile setup, explicit Activation, and Active employee authorization without introducing
another application path.

## CRA-49 Menu Source of Truth

```text
Admin Session + MFA + Organization/Location scope + CSRF
→ revision-guarded Draft hierarchy and item facts
→ JSON preview + explicit findings review + confirm-to-Draft
→ readiness revalidation + idempotent locked publication
→ previous Published archive + diff + safe audit in one transaction
→ Active Employee own Profile/Location → current Published Menu only
```

The accepted implementation stores one Menu per Location and immutable version snapshots with stable
section/category/item identity, Ukrainian canonical copy, optional English presentation fallback,
components, allergens, provenance, deltas, and Training-impact classification. Only a Draft is
mutable. Import confirmation never publishes; publication revalidates readiness and atomically
archives the previous current version.

`GET /api/v1/me/menu` and `GET /api/v1/me/menu/items/{item_id}` derive Organization and Location
from the authenticated user's single own Active Profile. They expose only the current Published
version and presentation-safe facts—never Drafts, import state, source checksums/references, actor
IDs, or a caller-selected tenant. Slice 2 applicability remains explicitly zero for Training
content, Assignments, and notifications.

## Accepted CRA-54 Training Content

```text
Admin Session + MFA + Organization/Location scope + CSRF
→ revision-guarded Training Draft with fixed Menu Module
→ typed Lessons and seven safe content block variants
→ private image intent + verification + short-lived signed access
→ readiness + current Published Menu dependency revalidation
→ idempotent locked publication + previous Published archive in one transaction
→ Active Employee own Profile/Location → current Published Training only
```

The accepted implementation stores one Training root per Location with immutable version
snapshots, one fixed Menu-domain Module per version, stable Lesson identity, canonical Ukrainian
copy, optional English
translation state, ordered typed content blocks, and private image assets. Only Draft versions are
mutable. Readiness blocks invalid canonical content, stale dependency/revision state, invalid Menu
Item links, unready images, missing alt text, and invalid external video identifiers; incomplete
English remains warning-only.

Admin routes derive and enforce Organization/Location scope, MFA, CSRF, optimistic revisions, and
idempotency where the operation can be retried. Publication locks and revalidates the Training root,
Draft, current Published version, and exact current Published Menu dependency before atomically
switching the Employee reference.

`GET /api/v1/me/training`, Module/Lesson detail routes, and private asset access derive Organization
and Location from the authenticated user's own Active Profile. They expose only the current
Published Training presentation, with entity/block locale fallback and no Draft, revision,
translation workflow, storage key, checksum, audit actor, or caller-selected tenant state.

The React frontend adds `/admin/content`, `/employee/learning`, Module detail, and Lesson detail.
React renders escaped editorial copy; image access uses the protected signed endpoint; external
video URLs are reconstructed only from validated YouTube identifiers and a fixed privacy origin.
Assignments, completions, progress, rollout, notifications, Practice, exams, and analytics remain
absent and publication reports zero Slice 4 counts.

## Accepted CRA-57 Assignment, Completion and Rollout

```text
version-owned audience + active Employee applicability
→ one current immutable-lineage Assignment per Training
→ explicit required Lesson Completion → derived Progress
→ replacement Publish → deterministic Rollout preview + preserve/repeat rules
→ locked atomic confirm → superseding Assignment + carried provenance
```

The accepted implementation replaces the Slice 3 current-Published-only Employee reference with
current-Assignment authority. Employee Home and Learning expose truthful progress and next action;
an assigned retained Version remains readable, media views never write, and Completion requires an
explicit protected mutation. Admin Employee detail supports assign/revoke/reassign. Admin Training
supports replacement-Version impact review, changed-Lesson preserve/repeat decisions, stale
recovery, and confirmed atomic Rollout. Provider-free background jobs are transactional and
deduplicated; no delivery worker or external provider call is added.

The accepted API currently has a revision-guarded audience replacement mutation but no audience
read contract. CRA-57 therefore does not add an unsafe browser editor that could overwrite
unknown existing role selections. Practice, Knowledge, Final Exam, scoring, certification,
deadlines, analytics, external delivery, and deployment remain absent.

## Test boundary

API tests run in-process through HTTPX ASGITransport. Persistence and migration tests require a
real dedicated PostgreSQL 16 database. See [`../testing/README.md`](../testing/README.md) and
[`../../.harness/TESTING.md`](../../.harness/TESTING.md).

## Explicitly absent

There is no invitation list/detail workflow, password recovery, MFA enrollment, Organization or
reference CRUD, Employee disable/reactivate lifecycle administration, Practice/exam workflow,
provider integration, or deployed worker/resource. The frontend lives in [`../../frontend/`](../../frontend/)
and includes accepted CRA-49/CRA-54/CRA-57 experiences. Adding any absent
capability requires a new bounded Linear issue and approval.
