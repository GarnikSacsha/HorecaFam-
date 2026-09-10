# CRA-149 — reference questions in Practice

## Accepted scope — 2026-09-09

Denys selected extending Practice to categories and descriptions. The accepted amendment is
recorded in [CRA-149](https://linear.app/craftspacee/issue/CRA-149/admit-source-verified-category-and-description-questions-to-practice),
the FINAL API contract and CRA-63. Only family admission changes: existing published
`menu.category` and `menu.description` join `menu.components` and `menu.allergens`.
Generation remains deterministic and requires verified source facts and Admin review/publication.
Unknown components/allergens remain unknown. No schema, API shape, provider or dependency changes.

Practice still requires ten distinct stable menu items, uses 40% for Final eligibility, and
reveals feedback only after finishing. Multiple families about one item count as one item.
Draft candidates and questions from another training version do not satisfy readiness.
Ten items allow Practice with a rotation warning; twenty distinct items support rotation.

## Local commit map; no commit authorization

1. `feat(backend): admit verified reference questions to Practice`: `backend/app/services/question_review.py`,
   `backend/tests/integration/test_practice_reference_families.py`,
   `backend/tests/integration/test_question_generation_service.py`.
   The existing mixed-family test now selects both questions for the same item explicitly.
2. `docs: record reference-question Practice acceptance`: this file, current-state additions to
   `STATUS.md`, `CONTEXT.md` and the existing staging preparation documents.

These boundaries do not authorize staging pre-existing changes in those documents. Preserve the
existing dirty worktree and empty Git index. Customer content under `outputs/` is excluded.

## Verification

RED on PostgreSQL 16: the first new case failed with `eligible_count == 0`, expected 9, after
successful generation and Admin publication. This establishes the old admission mismatch.
The first GREEN attempt then exposed a fixture collision with the one-published-training-version
constraint; the replacement-version check now follows archiving the first version.

Focused GREEN: **4 passed, 0 failed, 0 skipped** in 17.52s. Category-only and description-only
menus each generate ten candidates without composition/allergen facts. The tests prove draft
exclusion, nine-item blocking, ten-item admission, real Practice start/answer/finish, 30% denial
and exactly 40% earning Final eligibility, plus isolation from a replacement training version.
Ruff check and strict mypy passed on the changed implementation and tests.

Adjacent regression: **101 passed, 0 failed, 0 skipped** in 229.87s, including the four new
cases. Command from `backend/`, after the guarded test-environment load in `.harness/TESTING.md`:

```text
rtk ..\.venv\Scripts\python.exe -m pytest tests/unit/test_question_review.py tests/unit/test_question_generation.py tests/unit/test_assessment_readiness.py tests/unit/test_final_exam_contract.py tests/integration/test_practice_reference_families.py tests/integration/test_question_generation_service.py tests/integration/test_practice_attempt_service.py tests/integration/test_final_exam_service.py tests/integration/test_assessment_family_security.py tests/api/test_assessment_admin_api.py -q --tb=short -p no:cacheprovider
```

Protected-boundary review: only the allowlisted generation-rule codes change in production.
The same training-version and Published filters, explanation-source join, stable-item coverage,
readiness thresholds, attempt services and result/eligibility transaction remain in use. Adjacent
tenant/assessment security tests pass. No input-derived SQL or additional disclosure is introduced.
This is local test-database evidence; no full coverage rerun or hosted acceptance is claimed.

## Demo operation

After separately authorized publication and deployment of a candidate including CRA-149:

1. Import the reviewed menu through the existing supported Admin flow. The offline candidate
   packet is review material, not a server-import API.
2. Publish the intended menu and training version with menu-item lesson cards.
3. Generate question candidates through the existing service; review and publish category and
   description candidates covering at least ten distinct items (twenty for rotation).
4. Read Practice readiness for that exact training version. Resolve factual/publication gaps
   through Admin review; never infer missing ingredients or lower the coverage threshold.
5. Complete the assigned learning path as Employee, take Practice, and obtain at least 40%.
   Initial Final eligibility and Final question-pool readiness are separate gates.

The actual Bacara hosted path remains unrun. The selected staging SHA `fafec73` predates this
change; a reviewed replacement SHA is required before claiming this behavior in staging.
