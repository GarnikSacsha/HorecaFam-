# CRA-288 implementation commit map

Baseline prerequisite: `a5184b0`; see [baseline](cra-288-baseline.md).
Authority: CRA-288 and the current direct approval. This map excludes the separately completed
session-clock fix, admin/dashboard redesign, new dependencies, deployment and merge into main.

## 1. Position audiences and reusable training modules

Outcome: multiple non-menu modules in the existing versioned Training, with one/multiple/all
position audiences enforced by the backend for discovery, direct lesson/asset access,
completion, progress and assessment access. Existing Waiter modules retain their behavior.
Reuse OperationalRole; do not introduce a fixed three-position authorization enum.
Copy all modules and audiences when creating a new draft. Preserve historical results.

Expected paths: backend models/enums/training/training_assignments, training schemas/routes,
training draft/query/publication/audience/applicability/completion/progress and assessment
access services, an additive Alembic migration, corresponding API/integration/migration tests,
frontend training contracts and the existing module audience editor where required.
No content pack, Academy or broad visual redesign in this boundary.

RED: an existing authorized draft cannot create a non-menu module through the API.
GREEN: role visibility matrix, direct-access denial, tenant isolation, all-position behavior,
version-copy preservation, completion/progress and existing Training regression suites;
migration upgrade/metadata check, Ruff, mypy and affected frontend checks.

Commit: `feat(training): scope versioned modules to employee positions`.
Dependencies: confirmed baseline only.

## 2. Structured standards and course knowledge checks

Outcome: approved versioned non-menu rule provenance and course-scoped checks reuse the
existing question bank, snapshots and server grading. Preserve Interactive Training, Practice,
Final Exam thresholds, retake behavior and old attempts. Do not publish grading keys before
the allowed submission boundary.

Expected paths: backend standard-source models and services, assessment models/schemas/routes,
question review/provenance and attempt/result orchestration, additive migration, backend
security/integration/migration tests and frontend assessment contracts.
No separate test engine or certification policy.

RED/GREEN: unavailable new assessment family becomes a scoped, server-graded attempt;
cross-position/tenant denial, safe pre-submission payload, duplicate submission, old exam-family
isolation and history preservation; focused assessment suites, quality and migration checks.

Commit: `feat(assessment): add standards-backed course knowledge checks`.
Dependencies: stage 1.

## 3. Initial Runner, Bartender and shared training

Outcome: an explicit, repeat-safe content installation/import through the existing authoring/
operations workflow adds Runner and Bartender OperationalRoles and generic training content.
Runner has six topic units and about 15 scenario questions; Bartender has six topic units and
about 20 questions; shared Service Standards has eleven topic units and about 10 questions.
Keep source/review/publication boundaries. Do not overwrite existing Waiter material, infer
venue recipes/policies, or install demo content through schema migrations.

Expected paths: packaged backend training content, bounded authoring/operations integration,
training/question services as required, corresponding content and integration tests,
existing admin controls for invoking the bounded workflow.
Any changes to packaging merely include local content files; no dependency changes.

RED/GREEN: missing catalog/import behavior, then complete content counts and source links,
safe idempotent replay, assignment matrix, no overwrite, readiness and publication review.
Run relevant content/training/assessment tests and quality checks.

Commit: `feat(content): add runner bartender and shared service training`.
Dependencies: stages 1–2.

## 4. Optional Academy and focused employee navigation

Outcome: optional published articles, scoped to one/multiple/all positions, with category,
slug, summary, content, ordering and timestamps. Provide thirteen generic initial articles.
Reuse private media where a cover is supported. Reading articles never changes required
Training progress. Add only the navigation/pages and bounded admin controls necessary for
Training, Menu, Tests and Academy.

Expected paths: backend Academy models/schemas/routes/services, additive migration,
packaged article content and existing content-import integration, frontend API contracts,
employee Academy/navigation and focused admin authoring controls, backend/frontend/E2E tests.
Reuse existing visual language; no application-wide redesign.

RED/GREEN: unpublished/wrong-position/foreign articles are inaccessible; correct audiences
see published content; reading is optional; mutation guards and revisions remain safe.
Verify role-specific navigation and mobile layout with frontend and Playwright tests.

Commit: `feat(academy): add optional position-scoped articles and navigation`.
Dependencies: stages 1 and 3.

## Final acceptance

Run the full backend suite with independent coverage gates, all frontend tests and Playwright,
TypeScript/lint/format/build, and Alembic checks on the isolated local test DB. Perform a
separate fresh review pass of authorization, migration preservation, source provenance and
answer secrecy. Inspect the exact final diff and file inventory.

Record evidence and limitations in `docs/testing/`. Preserve atomic GREEN boundaries and
selective staging. Do not push, deploy or merge. Update remaining map entries before changing
their implementation boundary if new evidence requires it.
