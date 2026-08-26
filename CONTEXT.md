# HoReCa Project Context

## Purpose

HoReCaFam is the repository for the HoReCa Training Platform. The accepted implementation is
currently a minimal backend foundation; later identity, authentication, invitation, training,
and frontend work must be delivered through separate bounded Linear issues.

This document gives a new agent enough durable local context to orient safely. It intentionally
does not reproduce full product, API, data, RBAC, or test-stage contracts.

## Canonical product sources

Start with the Linear
[HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974),
then follow the source order it defines:

- [CRA-12](https://linear.app/craftspacee/issue/CRA-12/define-rest-api-contract-and-pydantic-schemas)
  for the final REST API contract and approved runtime behavior.
- [CRA-10](https://linear.app/craftspacee/issue/CRA-10/design-database-schema-and-entity-relationships)
  for the current database design, migration order, and RBAC where consistent with CRA-12.
- [CRA-13](https://linear.app/craftspacee/issue/CRA-13/define-backend-test-strategy-and-vertical-slice-acceptance-criteria)
  for backend test strategy and vertical-slice acceptance gates.
- The single active bounded Linear issue for exact scope, permissions, and evidence requirements.

Repository summaries are navigation aids. A consequential product/API/data/test decision is not
canonical until it is recorded in the applicable Linear source.

## Verified implementation boundary

[CRA-20](https://linear.app/craftspacee/issue/CRA-20/backend-mvp-vertical-slice-1-stage-0-api-foundation)
Stage 0 is accepted and Done. The repository contains:

- a Python 3.12 FastAPI application factory;
- the versioned `/api/v1` boundary and health route;
- request ID correlation and unified API errors;
- typed configuration;
- async SQLAlchemy 2 and asyncpg session infrastructure;
- Alembic with the empty-schema `0001_stage0` revision;
- fail-closed test database safety checks;
- API, unit, real-PostgreSQL integration, and migration tests;
- a reserved, empty frontend boundary.

No domain tables, identity persistence, authentication, invitation, employee lifecycle,
training workflow, or frontend application has been implemented.

## Repository map

- [`backend/app`](backend/app): accepted Stage 0 runtime foundation.
- [`backend/migrations`](backend/migrations): Alembic environment and Stage 0 base revision.
- [`backend/tests`](backend/tests): API, unit, integration, and migration tests.
- [`backend/pyproject.toml`](backend/pyproject.toml): Python requirements and tool configuration.
- [`frontend`](frontend): reserved boundary only.
- [`docs/architecture`](docs/architecture): verified local architecture summaries.
- [`docs/decisions`](docs/decisions): repository-local engineering decision index.
- [`docs/testing`](docs/testing): testing structure and accepted evidence index.
- `Photos/`: project assets for
  [CRA-19 Bacara Welcome / homepage](https://linear.app/craftspacee/issue/CRA-19/design-bacara-welcome-brand-intro-responsive-mockups),
  deferred from the initial backend/docs baseline and outside the accepted Stage 0 architecture
  boundary. Moving, renaming, optimizing, staging, or publishing them requires a separate bounded
  CRA-19 implementation/asset commit map.

## Current construction rule

Work proceeds by one bounded vertical stage at a time. Passing one stage permits only the next
explicitly approved planning or baseline action. See [`STATUS.md`](STATUS.md) for the current
checkpoint and next allowed step.
