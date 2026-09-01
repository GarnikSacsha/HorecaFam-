# MVP Vertical Slice 8 — Attention and Retakes local acceptance candidate

## Status

This document records the verified local CRA-71 implementation candidate on 2026-09-01.
Implementation start was authorized by Denys, but local commits, acceptance, publication, push,
PR, merge, provider activity and deployment remain unauthorized. The accepted remote baseline is
still **origin/main@9ef9fe1**; local **main@5352f89** is the prior CRA-70 documentation checkpoint.

## Implemented boundary

The candidate implements:

- Alembic head **0015_attention_retakes** with six tenant-owned Attention/Retake tables,
  constraints, indexes, deterministic historical backfill and reversible migration;
- immutable Critical Error projection from completed Practice/Final Exam Answers, stable subject
  identity, deduplicated unresolved critical Attention and append-only source/actions;
- one current seven-day Failed Final Exam Requirement, repeated-failure deadline preservation,
  scheduled/approaching/overdue/frozen timing, exact freeze/resume and qualifying completion;
- idempotent/concurrent deadline projection, source-linked overdue Attention and bounded automatic
  closure of only the linked operational overdue case;
- MFA/Admin/CSRF/idempotency/tenant-protected list/detail/propose/edit/confirm/cancel and
  acknowledge/resolve APIs with filter-bound opaque cursors and non-enumerating foreign IDs;
- own-only Employee Requirement/history and safe Attention summary without Admin comments, actors,
  target policy, grading keys or provenance;
- certified retake authorization only through a matching Active Requirement, including truthful
  blocking when no current source-safe critical Question exists;
- responsive **/admin/attention**, Results follow-up integration, calm Employee Home/Final Exam
  timing states and two complete three-viewport browser journeys.

Source Attempts, Answers, Results and certification remain immutable. Overdue never disables an
Employee. No leaderboard, combined score, bulk resolve, provider delivery, deployed scheduler,
generic Disable/Pause UI, real Bacara ingestion or CRA-19 asset work is included.

## CRA-13 Slice 8 scenario mapping

| Scenarios | Executable evidence |
| --- | --- |
| 1–15 persistence/backfill | test_attention_persistence_contract.py, test_migrations.py, 0015_attention_retakes.py |
| 16–30 lifecycle/timing/concurrency | test_retake_lifecycle.py, test_final_exam_service.py |
| 31–40 completion/critical matching | test_retake_lifecycle.py, test_attention_workflow.py, Final Exam/Practice service tests |
| 41–55 Attention/API/security | test_attention_workflow.py, test_attention_admin_api.py, test_employee_follow_up_api.py |
| 56–62 frontend states/Admin workflows | AdminAttentionPage.test.tsx, existing Home/Final Exam component regression |
| 63–64 browser journeys | attention-retakes-slice.spec.ts on all three configured Playwright projects |
| 65 full gate/inventory | full backend/frontend/migration/browser commands and final inventory below |

The additional UX-contract RED reproduced **422 VALIDATION_ERROR** when Admin creation omitted an
internal Assessment UUID. GREEN derives the current Final Exam target inside the verified
Organization/Employee/source/Assignment boundary; the focused PostgreSQL test then passed.

## Executed evidence

- Python 3.12.10 and real dedicated PostgreSQL 16 test database.
- Ruff format check: 199 files formatted; Ruff check passed.
- Strict mypy: 181 source files passed.
- Focused Slice 8/adjacent PostgreSQL gate: 33 passed, 0 failed, 0 skipped.
- Full backend regression: 463 passed, 0 failed, 0 skipped in 1145.80 seconds.
- Overall statement/branch coverage: 86%.
- Alembic: upgrade/current/no-drift passed at **0015_attention_retakes**; migration suite proves
  empty upgrade, downgrade/upgrade, deterministic backfill and immutable source preservation.
- Prettier, TypeScript and ESLint passed.
- Vitest: 19 files, 58 passed, 0 failed, 0 skipped.
- Production Vite build passed.
- Focused Slice 8 Playwright: 6 passed across 1440×1000, 768×1024 and 375×812.
- Full Playwright regression: 27 passed, 0 failed, 0 skipped.

## Remaining gates

- Denys has not yet accepted this candidate or authorized any local commit.
- The agreed eight checkpoint boundaries remain unstaged and uncommitted.
- Linear checkpoint/final evidence publication requires a separate explicit external-write
  authorization.
- Railway cron/worker scheduling, provider delivery, staging, production and pilot hardening are
  outside CRA-71.
