# SQLAlchemy asyncio runtime recovery — 2026-09-28

## Authority and bounded commit map

Denys explicitly approved the SQLAlchemy asyncio dependency correction, one corrective
commit, push/merge and API redeployment after the failed CRA-275 delivery. This is the
bounded CRA-275 recovery continuation; no backend product-contract expansion.

Commit: `fix(backend): install SQLAlchemy asyncio runtime dependencies`.
Paths: backend/pyproject.toml, this report, STATUS.md.
Verification: clean Python 3.12 production-only install, real async RED/GREEN,
installed-package app factory/lifespan and API startup health, pip check,
existing health tests, exact staged inventory and diff hygiene.

## Cause and minimal correction

PR #1 merged as 811ea0598ef2e432938d54f836af8545c5163e09. Web deployment
fc46b8c4-7b1b-4a68-afc7-35991f1a9d55 succeeded; public smoke passed 11/0/0.
The API deployment 89138ef2-668b-4e85-b8f2-3345a7153adb could not start:
SQLAlchemy asyncio required greenlet, absent from the fresh production install.
Previous API 0aefad8b-aed6-456e-9e1c-35b637f3272e remained SUCCESS.

Docker installs the production project using pip install . . Existing development
environments can retain greenlet and therefore hide an incomplete runtime declaration.
The original range resolved SQLAlchemy 2.1.1 in a clean Python 3.12.10 environment,
and importing sqlalchemy.ext.asyncio failed with the same missing-greenlet error.

Changed only `sqlalchemy>=2.0,<3` to `sqlalchemy[asyncio]>=2.0,<3`.
Keep the accepted version range; the provider's asyncio extra declares its required
runtime dependency. No broad version upgrade, lockfile, Docker/configuration, API,
schema, migration or data change.

## RED and GREEN evidence

An isolated copy contained 157 tracked Docker build-input files, excluding environment
files, tests, caches and local runtime data. A fresh venv installed this production
project without test extras. Before the correction, actual async execution failed
at import: 0 passed / 1 failed / 0 skipped. This was the intended packaging RED.

After changing the extra, the same production installation was rebuilt through pip:
SQLAlchemy 2.1.1 with greenlet 3.5.6. No manual greenlet installation was used.
The installed package (site-packages, isolated Python mode) passed:

- greenlet-backed async execution;
- create_app plus application lifespan;
- a separate API process on a free loopback port, GET /api/v1/health -> 200 and
  the exact approved status body. The process was stopped after the check.

Production smoke: 3 passed / 0 failed / 0 skipped. pip check: no broken requirements.
Existing tests/api/test_health.py: 2 passed / 0 failed / 0 skipped in 0.66 seconds.
The smoke used synthetic test configuration and did not connect to or mutate a database.
No full backend/frontend suite or Linux Docker run is claimed for this dependency-only
correction. The earlier full backend 994/0/0 belongs to the prior audit, not this fix.

Local verification files and venv remain under outputs/sqlalchemy-runtime-2026-09-28
and are excluded from Git. No generated helper is production source.

## Review and delivery

Fresh review confirms one dependency-extra change, unchanged dependency version range,
no application logic or protected data-boundary change. Existing health tests and real
production-package smoke cover the failure path; tests installed in the development
environment alone would not prove this correction.

Push the corrective branch, review its exact diff, merge without rewriting checkpoint
history and observe API startup/health in Railway. Existing GitHub source bindings may
also rebuild web; verify resulting deployments. No source/settings/secret changes,
migration, content-v5 publication, assessment recovery or employee rollout is included.
Post-merge delivery results are recorded in canonical Linear CRA-275 and START HERE;
this file records the verified pre-delivery checkpoint.
