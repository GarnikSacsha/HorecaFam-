# Railway topology

`railway.ts` is the repository-owned desired topology for CRA-119. It declares PostgreSQL plus
separate API, worker, and web services. Secret values use `preserve()` and remain provider-owned.

This file is intentionally not applied by CRA-119. After the implementation is accepted and
published, a separately authorized provisioning task must:

1. install a compatible Railway CLI and run `npm ci` in this directory;
2. link the exact approved Railway project and environment;
3. set or import every preserved variable from `docs/deployment/environment.md`;
4. run and review `railway config plan` without exposing preserved values;
5. obtain a separate approval before any `railway config apply`;
6. run Alembic `upgrade head` as an explicit one-off release command before switching traffic;
7. execute API, worker, frontend, email, rollback, backup, and restore smoke evidence.

Railway Infrastructure as Code is experimental. Keep the SDK pinned, review its changelog before
upgrading, and never treat a local typecheck as provider-side plan or apply evidence.
