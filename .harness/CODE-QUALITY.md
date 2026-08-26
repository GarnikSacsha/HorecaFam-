# HoReCa Code Quality Contract

AI-generated code is untrusted until the real path has been understood, tested, reviewed, and
accepted inside an active bounded Linear issue.

## Required development cycle

For every behavior-changing code task:

1. Trace the current execution path and its canonical Linear contract.
2. Write or update the smallest meaningful behavior test.
3. Run it before implementation and confirm an intended `RED`.
4. Implement only enough coherent behavior to reach `GREEN`.
5. Refactor for clarity while keeping target and adjacent checks green.
6. Review the final file inventory and diff before handoff.
7. Record exact RED, GREEN, refactor, and adjacent-check evidence in the bounded issue.

An import, syntax, fixture, credential, or unrelated environment failure is not a valid RED. Do
not weaken assertions, delete tests, or mock away the production route merely to obtain GREEN.

## Documentation-only exception

Documentation/configuration hygiene may declare a TDD exception before edits when no runtime
behavior changes. Alternative evidence must include source routing, internal links, command audit,
secret/local-path scan, exact file inventory, and diff hygiene. Do not claim production tests were
rerun unless they actually ran.

## Language and readability

- Identifiers, modules, packages, types, API fields, database objects, configuration keys, and
  machine-readable contracts are English.
- New explanatory comments and docstrings are Ukrainian. Explain a non-obvious reason, invariant,
  business rule, compatibility boundary, or failure behavior rather than narrating syntax.
- Existing accepted English docstrings are not rewritten during unrelated work.
- Prefer small typed boundaries and the existing project architecture over speculative layers.
- Do not add a dependency, framework, queue, cache, or provider without demonstrated need and
  separate approval.

## Review gate

Every material implementation requires self-review after tests. Database, migration, identity,
authentication, authorization, secrets, customer data, provider, infrastructure, or broad changes
also require an independent reviewer or a clearly separated fresh review pass.

Review separately:

- correctness and user-visible behavior;
- errors, retries, concurrency, and partial failure;
- authorization, data isolation, secrets, and side effects;
- architecture fit, migration safety, duplication, and coupling;
- readability, comments, dead code, and unnecessary abstraction;
- test quality, negative cases, false-green risk, observability, and rollback.

Critical and high findings block acceptance. Medium findings require an explicit owner and
decision. Low findings may be deferred with rationale.

Use the verified commands in [`TESTING.md`](TESTING.md). Never report a check as passed when it
was skipped, blocked, or not executed.
