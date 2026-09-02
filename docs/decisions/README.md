# Repository Decision Records

This directory is reserved for concise, accepted repository-local engineering decisions whose
consequences would otherwise be rediscovered from code or chat.

## Boundary with Linear

Do not create local ADRs that redefine product behavior, API schemas, entities, lifecycle states,
RBAC, acceptance gates, roadmap, or stage scope. Those decisions remain canonical in the Linear
[HoReCa Agent Implementation Index](https://linear.app/craftspacee/document/start-here-horeca-agent-implementation-index-cde401714974)
and its routed issues.

A local decision record may cover matters such as repository layout, an approved replaceable
engineering mechanism, or a development workflow when:

- the decision is accepted by Denys;
- it is consequential or costly to reverse;
- it does not compete with a canonical Linear source;
- evidence, alternatives, consequences, and revisit conditions are known.

Each record uses a numbered English filename and includes status, date, scope, evidence, decision,
consequences, alternatives, and a Linear reference where applicable. Proposed decisions are not
implementation authority.

## Current index

No standalone repository ADR exists yet. CRA-20 implementation decisions, CRA-21 baseline scope
and CRA-77 Operations/Hardening choices remain recorded in their canonical Linear issues and
verified code/tests. The locally accepted CRA-77 range did not introduce a separately accepted
repository-local architectural decision. Add the first record only when a future bounded issue
explicitly accepts one.
