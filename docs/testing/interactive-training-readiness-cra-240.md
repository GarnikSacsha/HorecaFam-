# CRA-240 — Interactive Training readiness family isolation

Hosted follow-up: owner-approved staging API delivery completed successfully; all three readiness
GETs and public API health return 200. See [delivery evidence](../deployment/readiness-fix-cra-240.md).
The local-only approval boundaries below describe the earlier implementation stage.

## Scope and contract

On 2026-09-16 Denys approved a focused local regression test and backend correction for
the CRA-239 post-generation lesson-readiness failure. No commit or deployment is authorized.
Canonical scope: [CRA-240](https://linear.app/craftspacee/issue/CRA-240/restrict-lesson-readiness-to-interactive-training-assessments)
and the FINAL CRA-12 per-Lesson readiness contract. Practice and Final Exam retain their
separate readiness endpoints and thresholds. No API schema or product contract changes.

## Reproduction and correction

The lesson query selected every Published AssessmentVersion for the requested TrainingVersion.
Normal candidate generation creates Practice and Final Exam configurations with null lesson
identifiers. These rows failed validation against the lesson readiness response's required UUIDs.

The dedicated PostgreSQL regression invokes the real Practice/Final readiness creation services,
then reads lesson readiness both without and with a lesson-readiness row. Both cases failed before
the correction with required lesson UUID validation errors. Organization/location negative cases
returned the expected RESOURCE_NOT_FOUND. RED: 2 failed, 2 passed, 0 skipped, 10.55 seconds.

The correction joins Assessment by its primary key and filters assessment_type to
interactive_training. The existing scoped TrainingVersion lookup, exact TrainingVersion and
Published filters, ordering, response fields and readiness semantics remain unchanged.
No exception swallowing, nullable-schema workaround, migration or data repair is introduced.

## Verification

Exact RED command repeated after the fix and formatting: 4 passed, 0 failed, 0 skipped in
18.74 seconds. This is the same four cases included in the combined suite, not additional coverage.
Relevant combined suite: 67 passed, 0 failed, 0 skipped in 128.98 seconds. Includes the four
new regressions, question generation, assessment-family security, Practice reference families,
Final Exam services, assessment Admin API, question review and readiness unit cases.
Ruff format: 262 files formatted after correcting the new test's line wrapping; Ruff check passes.
Strict mypy: 240 source files, no issues. Git diff whitespace check passes. No full repository
coverage or fresh hosted acceptance is claimed.

Commands from backend, with the guarded test environment procedure in
[TESTING.md](../../.harness/TESTING.md):

```powershell
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_interactive_training_readiness.py -vv -p no:cacheprovider --tb=no --show-capture=no
rtk ..\.venv\Scripts\python.exe -m pytest tests/integration/test_interactive_training_readiness.py tests/integration/test_question_generation_service.py tests/integration/test_assessment_family_security.py tests/integration/test_practice_reference_families.py tests/integration/test_final_exam_service.py tests/api/test_assessment_admin_api.py tests/unit/test_question_review.py tests/unit/test_assessment_readiness.py -vv -p no:cacheprovider --tb=no --show-capture=no
rtk ..\.venv\Scripts\python.exe -m ruff format --check .
rtk ..\.venv\Scripts\python.exe -m ruff check .
rtk ..\.venv\Scripts\python.exe -m mypy app tests
```

## Separated review

After implementation, reviewed the route's Organization Admin dependency, scoped TrainingVersion
lookup, query diff and database composite foreign keys. The join has one parent per version and
adds no writes or side effects. Tenant ownership remains checked before the query; existing
assessment/training scope foreign keys remain intact. No high or critical issue found in this
bounded change. Synthetic test fixtures reuse the existing assessment factory context.

## Commit boundary and handoff

The next preparation step is complete: [isolated API packet and delivery plan](../deployment/readiness-fix-cra-240.md).
Candidate verification: 9 passed, 0 failed/skipped; 386 manifest/ZIP files match after tests.
Deployment still requires separate approval.

One future selective GREEN commit: backend/app/services/question_review.py,
backend/tests/integration/test_interactive_training_readiness.py, this report, and only the
CRA-240 STATUS.md hunk. STATUS.md already contains separate uncommitted reconciliation changes;
do not stage that whole file indiscriminately. No index, commit, push or deployment was performed.

Hosted CRA-239 remains blocked until separately approved delivery and fresh endpoint verification.
The existing 80 candidates must not be regenerated. Candidate review/publication and Employee
Learning/Practice/Final/Results acceptance remain subsequent steps. The frontend's stale readiness
display on a failed refresh is a separate recorded limitation, outside this correction.
