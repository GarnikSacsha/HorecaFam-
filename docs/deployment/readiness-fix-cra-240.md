# CRA-240 — Prepared API delivery

## Authorized delivery completed — 2026-09-16

Denys explicitly approved this packet's staging API rollout and read-only smoke. Before upload,
386 source hashes and the archive hash matched; current API deployment matched the CRA-237 base.
Railway deployment c346bfcb-8526-4c56-b399-0daed5154c75 is SUCCESS. Build root /backend,
Dockerfile, API start command and healthcheck remained unchanged.

Fresh authenticated Admin refresh at 15:37 UTC removed the Question Bank loading error.
API logs confirm interactive-training, practice and final-exam readiness each returned HTTP 200;
public API health also returned 200: 4 HTTP checks passed, 0 failed/skipped.
The existing 80-candidate queue remains; no candidates were generated, edited or approved.
Lesson readiness currently has zero configured assessments; Practice is blocked at 0/10 and
Final at 0/20 with INSUFFICIENT_QUESTION_POOL. These are current content readiness blockers,
not the previous HTTP 500. Full Employee acceptance is still pending reviewed question publication.

No web/worker/cron rollout, migration, settings change, Git commit or push occurred.
Initial sandbox network access failed; authorized network access succeeded. One local log
wrapper could not locate the CLI executable; the corrected CLI call verified the statuses above.
The preparation and proposed-operation sections below are retained as the approved plan.

Prepared on 2026-09-16 following Denys's request to execute the next preparation step.
This document does not authorize deployment. No application code changed during preparation.

## Exact candidate

Local artifact: outputs/cra-240-candidate-2026-09-16/source.zip.
SHA-256: 09268a07a0bf6bf620b34769b72f2780d2797ac7e5a8ccc76d9031225898925c.
Manifest and source directory are beside the ZIP. All 386 files were verified both in the
source tree and ZIP after tests: zero mismatches or extras.

Base: sealed CRA-237 source, recorded API deployment 180b0d82-c1cb-476a-baff-76d5575293ec.
All 385 base files and its ZIP hash were verified before assembly. Overlay contains only:

- backend/app/services/question_review.py: two added query lines.
- backend/tests/integration/test_interactive_training_readiness.py: four regression cases.

The packet preserves the deployed backend baseline and excludes local CRA-234 corrections.
Its historical frontend files are not selected for deployment; the current CRA-238 web stays in place.
No dependency, Dockerfile, settings, migration or schema changes.

## Verification

From the candidate backend itself: 9 passed, 0 failed, 0 skipped in 18.92 seconds.
Selection: new lesson-readiness integration tests, PostgreSQL round trip/version check,
and assessment Admin API tests. Import-path assertion confirmed the candidate's service was loaded.
The guarded existing dedicated test environment was loaded without copying secrets into the packet.
Bytecode/cache output was disabled. No dependency installation or remote build was performed.
Prior checkout evidence: [67 relevant tests and quality checks](../testing/interactive-training-readiness-cra-240.md).

## Proposed operation for approval

1. Reverify manifest/hash and read current staging API service/deployment/settings metadata.
   If its deployed baseline differs from the recorded CRA-237 baseline, stop and reconcile first.
2. Upload only the prepared source to existing project 04320f63-ab40-426f-ab35-02fcb365c3b8,
   staging environment d8e64109-9863-4faa-a45e-f072adb3cfac,
   API service 785ae5f7-9052-4a1b-92ea-e8524236de97. Preserve existing backend build root,
   start command, variables and health check; use the established isolated path-as-root workflow.
3. Wait for successful API build/deployment and public API health 200.
4. In the authenticated Admin session, refresh the existing question workspace. Verify lesson,
   Practice and Final readiness all return 200; the existing 80 candidates remain available.
   Do not generate, approve or publish questions during this smoke check.
5. Record the new deployment and observations. If build or smoke fails, stop content operations;
   retain the exact prior deployment identifier for owner-approved rollback. No database rollback
   is required by this read-only query change.

Approval scope: this API rollout and read-only smoke only. Web, worker, cron, migrations,
candidate publication, Git commits and pushes remain separate. Successful smoke enables the
question-review step; it does not establish complete Employee or venue acceptance.
