# CRA-288: standards-backed course checks

This is commit-map stage 2, following `0ef61b5`. The original backend/auth baseline is
recorded separately in [the baseline report](cra-288-baseline.md).

## Behavior and contracts

Versioned, location-scoped standard sets contain verified scenarios, allowed actions,
prohibited alternatives, conditions, order and provenance. Published source versions are
immutable at the database boundary. A Training module pins its source version; draft cloning
preserves that pin. Deterministic generation creates review candidates, never approved tests.
The existing Admin question bank provides generation and human review.

Course knowledge checks reuse question versions, pools, attempt snapshots, grading and device
leases. They contain 1–20 questions (supporting the requested 10/15/20 packs), require the
module's required lessons, and return a server-calculated knowledge score after explicit
submission. They do not award Final Exam certification or introduce a pass threshold.
Existing Interactive Training, Practice, Final Exam and retake rules are unchanged.

Employee course endpoints are under `/me/training/course/attempts`; starting uses the assigned
module-version ID. Discovery, direct access and writes enforce position, tenant, ownership,
membership, assignment, CSRF and device lease boundaries. Before finish, responses contain
neither grading keys nor explanations. Retries reuse idempotency keys.

Migrations 0023 and 0024 add assessment-family consistency and standard source provenance.
Legacy rows are backfilled from their parent family. Composite foreign keys prevent treating
a 20-question course as a Final Exam. Lossy downgrade is refused when new content exists.

## TDD and verification

- Persistence RED: course family/counts rejected by the existing constraints; GREEN after
  additive family constraints and the actual-count trigger were updated.
- Standards RED: five missing tables, four missing immutability boundaries and missing
  deterministic candidate generation; GREEN with source schema, triggers and generation.
- Draft-copy RED: pinned standard dependency lost; GREEN after copying the dependency.
- API/UI RED: absent course endpoints, explicit finish action and standards generation;
  GREEN with backend orchestration and focused existing-screen extensions.
- Expanded backend suite: **444 passed, 0 failed, 0 skipped** (407.42 seconds), including
  unit, course/admin/employee APIs, source/persistence/family security, Interactive Training,
  Practice, Final Exam and all migrations.
- Full frontend: **171 passed**, 32 files. TypeScript, ESLint, Prettier and build passed.
- Full Playwright: **90 passed**, all three configured viewports. Mock API browser checks
  do not claim real staging acceptance. Mobile course screenshot inspected.
- Ruff and strict mypy passed (274 source files). Existing large-bundle warning remains.
- Additional course API run: **12 passed, 0 failed, 0 skipped**, including two-session
  takeover, one-time idempotent generation increment and rejection of the previous writer.
  Its first run had one fixture error (duplicate unique CSRF hash) and 11 passes; unique
  test-session CSRF values fixed setup before the complete 12-test rerun.

## Separate fresh review

Reviewed family constraints and backfill/downgrade order, source immutability and tenant keys,
question provenance, explicit answer-release boundary, server score arithmetic, active
assignment checks, transaction locks, idempotency and device ownership. Legacy family tests
now construct explicitly typed attempts; assertions and business rules were retained.

No production/staging operations, dependency installs, pushes or merges. Runtime evidence and
local test environment remain outside Git. Initial content packs and Academy are later commit
boundaries; this stage alone does not complete CRA-288. Final full backend coverage must be
rerun after all stages.
