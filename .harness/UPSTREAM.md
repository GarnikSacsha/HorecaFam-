# Global Harness Upstream

## Pinned source

- Repository: [GarnikSacsha/denys-agent-harness](https://github.com/GarnikSacsha/denys-agent-harness)
- Branch read: `main`
- Exact commit read: [`3eaa9586b4e09e70399c2600aa1808b18449a15d`](https://github.com/GarnikSacsha/denys-agent-harness/tree/3eaa9586b4e09e70399c2600aa1808b18449a15d)
- Read date: 2026-08-26
- Review scope: all 31 files at the pinned commit, including the operating contract, context
  router, policies, security and quality standards, workflows, templates, skills, and scripts.

This SHA records the evidence used to prepare the HoReCa project context. It is not a Git
submodule, dependency, vendored package, or automatic update channel.

## Adapted principles

HoReCa adopts the upstream read-first protocol, bounded autonomy, approval gates, dirty-worktree
safety, `RED → GREEN → REFACTOR`, independent review for protected boundaries, least privilege,
environment separation, exact evidence, concise context routing, and factual handoffs.

The updated upstream also supplies the atomic commit model adopted for HoReCa:

- define an ordered commit map before implementation;
- treat one completed verified GREEN stage as one atomic recoverable commit;
- let one explicit bounded local-commit authorization cover the agreed map only;
- record RED as TDD evidence without committing a broken RED state;
- inspect exact diffs and stage exact paths rather than using `git add .`;
- preserve accepted checkpoints unless Denys separately approves history rewriting.

HoReCa adds project-specific rules required by its accepted sources:

- Linear is canonical for product/API/data/RBAC/test-stage decisions.
- Every task uses one active bounded Linear issue.
- Backend work always requires an explicit read of `backend/AGENTS.md`.
- Identifiers and machine-readable contracts are English.
- New explanatory comments and docstrings are Ukrainian.
- `Photos/` is protected CRA-19 homepage project material and is excluded from the initial
  backend/docs baseline unless a separate approved commit map explicitly includes it.

## Intentional omissions

The repository does not mechanically copy upstream profile/history files, reusable project
patterns, templates, skills, provider adapters, bootstrap scripts, or validation scripts. Those
files are useful upstream tooling, but they are not HoReCa product truth and would create duplicate
or stale context here.

No upstream `LICENSE` is copied. No licensing decision for HoReCa is implied.

## Refresh procedure

Updating this pin requires a separate read-only comparison against the then-current upstream
`main`, an exact new SHA, a summary of material rule changes, and Denys approval before project
instructions change. Never replace the adapted files by running the upstream bootstrap script.
