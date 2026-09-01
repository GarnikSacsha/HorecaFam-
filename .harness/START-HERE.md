# HoReCa Context Router

Read [`../AGENTS.md`](../AGENTS.md) first. It is the mandatory repository entry point.

## Mandatory Linear entry

Before substantive work, read the Linear
[START HERE — HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974),
the single active bounded issue, and every canonical source named by that issue.

If there is no explicitly active bounded issue authorizing the requested action, stop before edits.

## Task routing

| Task | Read next |
|---|---|
| Repository orientation or new chat | [`../CONTEXT.md`](../CONTEXT.md), [`../STATUS.md`](../STATUS.md), Git state |
| Any backend task | [`../backend/AGENTS.md`](../backend/AGENTS.md), relevant code/tests, active Linear issue |
| Behavior-changing implementation | [`CODE-QUALITY.md`](CODE-QUALITY.md), [`TESTING.md`](TESTING.md) |
| Database, auth, identity, secrets, providers, infrastructure | [`SECURITY.md`](SECURITY.md), canonical Linear data/API sources |
| Git baseline, commit, branch, push, or handoff | [`GIT-WORKFLOW.md`](GIT-WORKFLOW.md), [`../STATUS.md`](../STATUS.md) |
| Architecture review | [`../docs/architecture/README.md`](../docs/architecture/README.md), current runtime path |
| Testing or acceptance evidence | [`TESTING.md`](TESTING.md), [`../docs/testing/README.md`](../docs/testing/README.md) |
| Operations, worker, audit, bootstrap, pilot hardening | [`SECURITY.md`](SECURITY.md), [`../docs/testing/operations-hardening-slice-9-acceptance.md`](../docs/testing/operations-hardening-slice-9-acceptance.md), active Linear issue |
| Consequential engineering decision | [`../docs/decisions/README.md`](../docs/decisions/README.md) |

Agents launched from the repository root must explicitly read `backend/AGENTS.md` before backend
work. Do not assume that nested instructions were discovered automatically.

## Source boundary

- Linear owns product behavior, API/data/RBAC contracts, stage gates, scope, and approvals.
- Code, tests, migrations, and runtime evidence prove what is currently implemented.
- Repository docs route and summarize; they do not silently redefine canonical contracts.
- The global harness supplies operating principles, not HoReCa product facts. Its pinned source is
  recorded in [`UPSTREAM.md`](UPSTREAM.md).

When a repository summary conflicts with Linear, stop, identify the exact conflict, and update
neither contract nor implementation until Denys approves the resolution.
