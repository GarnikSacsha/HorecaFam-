# Demo continuation after the September 16 audit

## Authorized continuation — 2026-09-17

This checkpoint supersedes earlier generation/publication and readiness-blocker wording below.
Denys authorized autonomous execution of the audited demo continuation. CRA-239 owns the
review/publication operation; CRA-122 retains overall staging and walkthrough acceptance.
CRA-240 hosted correction was already delivered; no repeat deployment was needed.

Documentation checkpoint map, defined before these edits:

- Outcome: record the source review, completed publication, actual readiness and remaining
  Employee-session boundary in `STATUS.md` and this report.
- Verification: current Admin UI evidence, exact added text, relative-link targets and
  `git diff --check`; documentation-only TDD exception applies.
- Intended future boundary: `docs: record reviewed demo question publication`.
  Existing unrelated/preexisting hunks must be reviewed separately; no index change or commit
  is authorized by this checkpoint. Production code, dependencies, migrations, deployment,
  Photos and runtime output are excluded.

### Source review and publication

Read all 308 Published Menu v1 items and all 80 existing revision-zero candidates through the
authenticated Admin UI. Every candidate matched either the exact source category or source
description, resolved to one source item, had one marked answer, unique option labels and
correct-fact/distractor provenance. Result: 80 passed comparisons, 0 failed; these are content
checks, not automated application tests. The bank contains 40 category and 40 description
questions across four lesson scopes (24/24/10/22), covering 27 distinct source items.
Cross-lesson repetition is retained. No structured composition/allergen facts were inferred.
No raw question text, customer records, identity or credential is copied into this report.

Selected the reviewed 80 and submitted one normal Admin batch approval. While pending, the
button was disabled; the request was not repeated. The resulting UI confirmed `80` approved
and 0 candidates in the needs-review queue. Published Menu/Training versions remain v1;
there was no regeneration, source republication or candidate edit.

| Fresh hosted readiness | Observed result |
| --- | --- |
| Interactive lessons | 4/4 ready; question pools 10/24/24/22, minimum 5 each |
| Practice | Ready; 27 distinct source items, minimum 10 |
| Final Exam | Ready; 80 published questions, minimum 20 |
| Rotation | Supported for all four lessons, Practice and Final |

### Employee boundary and remaining work

The Admin Employee card shows an active account, active learning and an existing assignment
to the same Published Training v1. Progress is 0/4 required lessons, 0%. No assignment or
activation write was necessary. Both accessible Chrome profiles were verified as Admin
sessions. No authenticated Employee session was available, so the Employee journey was not
started. Credentials were not read, reset or changed; no invitation or email was sent.

Next: use ordinary Employee sign-in, complete the four assigned lessons and their Interactive
checks, Practice, Final and Results verification, then obtain the owner walkthrough acceptance.
Readiness is not successful Employee execution or full staging/pilot acceptance. This demo
question set covers 27 of the 308 source items; it does not certify full-menu knowledge.
CRA-234 delivery, broader staging gates and Git publication keep their separate boundaries.

Only the two mapped documents are changed by this checkpoint. No application suite was run
because no application code changed; the prior CRA-240 tests remain dated evidence.
Verification: 48 relative-link targets checked, 0 missing; `git diff --check` passed (only
existing LF/CRLF conversion warnings). Linear CRA-239 and START HERE were read back after
updates; CRA-239 has no remaining CRA-240 blocking relation and stays In Progress. CRA-122
also records the same current checkpoint. Git index remains empty; the 36-entry worktree
inventory is preserved.

## Scope and checkpoint boundary

Denys requested the audited follow-up in order. CRA-122 owns this documentation reconciliation;
product contracts and acceptance states are preserved. The documentation-only TDD exception
applies: verify source routing, links, current evidence, exact diff and safe file inventory.
No application tests are claimed for these documentation edits.

One proposed documentation checkpoint, `docs: reconcile published training and demo next steps`:
`STATUS.md`, `README.md`, `CONTEXT.md`, `backend/README.md`,
`docs/architecture/README.md`, `docs/testing/README.md`, this report,
`docs/testing/training-menu-picker-cra-238.md`, and the four existing deployment entry documents:
`staging-cra-122.md`, `staging-acceptance-cra-122.md`,
`cra-122-source-build-preparation.md`, `staging-preflight-2026-09-12.md`.
Verification: exact source/readback, relative links and diff hygiene. No staging or local commit
is performed; CRA-237/238 implementation maps retain their separate source boundaries.

## Recovered and fresh evidence

The initial audit relied on the implementation-only CRA-238 report. The preceding completed
task subsequently recorded explicit web rollout approval, successful delivery, live picker use,
four populated lessons and separately approved Training publication. This later evidence
supersedes the proposed repeat rollout and lesson-authoring steps.

Fresh read-only checks in this continuation:

- Public staging HTML returns 200 and references CRA-238 `index-DEGtw7P2.js`.
- Authenticated Training UI shows Published v1 and no Draft.
- Question Bank shows an empty review queue, no assessment configuration, Practice 0/10 and
  Final 0/20 with `ASSESSMENT_NOT_CONFIGURED`. No generation, review or publication is implied.
- The 0/0 lesson-readiness display belongs to absent assessment configuration; it must not
  overwrite the independently established four-lesson publication evidence.
- Global checkout and direct upstream remain at pinned `3eaa958`; the checkout is clean.
- Local main is `bf4790c`, 32 commits ahead / 0 behind directly read GitHub `fafec73`.

The [CRA-238 report](training-menu-picker-cra-238.md) now includes the previously missing
delivery/hosted continuation. [STATUS](../../STATUS.md) is the sole current state summary;
entry documents route to it rather than repeating changing content counts.

## Ordered remaining path

1. Inspect the generation contract and existing Published Menu/Training source binding. Generate
   candidates only for those sources; this is distinct from approving or publishing questions.
2. Review question wording, unique correct answer and provenance against the source. Reject
   ambiguous questions and any inferred ingredient/allergen claim. Preserve unknown facts.
3. Publish only the reviewed candidate selection through the normal confirmation flow. Verify
   each lesson's five-question readiness, ten distinct Practice items and twenty Final questions;
   inspect rotation limits separately. Offline counts are not hosted readiness.
4. Inspect assignment state first: Training publication may already affect applicability. Do not
   blindly create duplicate assignments. Continue the existing active Employee through Learning,
   Interactive, Practice, Final and Results using normal account/session controls.
5. Record the actual Admin/Employee result and obtain Alexandra's walkthrough acceptance.

Remaining independent work: source-based fact confirmation UI, investigation of the audience
revision conflict if reproduced, separately reviewed CRA-234 delivery, selective source commits
and GitHub publication. Wider pilot gates include real storage/recovery-provider checks, cron
acceptance, load, isolated restore and accessibility. Do not reopen completed provisioning,
activation, Menu import, CRA-238 delivery or Training publication.

## Limits

The documentation checkpoint changes documentation and Linear navigation only. No code, dependency,
schema, provider configuration, deployment, content write, Git index or commit changes occur
in this checkpoint. Existing customer artifacts, Photos, runtime output and other worktrees
remain excluded. Recorded application tests are dated evidence, not fresh regression results.

## Documentation verification

Twelve mapped documents: 245 relative links resolved, zero missing targets. Targeted credential
and local-path pattern scan flagged zero files. `git diff --check` passed. Exact documentation
diff was reviewed; pre-existing source changes remain outside this checkpoint. Five Linear
records were read back: START HERE, two-person demo roadmap, CRA-122, CRA-237 and CRA-238.
Their new leading checkpoint is present and issue statuses remain In Progress. One CRA-122
save returned a transient 502; readback proved it had applied, so no duplicate prepend occurred.
No application test suite ran for this documentation-only checkpoint.

## Subsequent CRA-239 operation and blocker

After the documentation checkpoint, the next bounded operational issue is
[CRA-239](https://linear.app/craftspacee/issue/CRA-239).
All-status inventory was empty. One explicit normal Admin generation action reported:
80 created, 0 existing, 0 stale. The UI displayed 80 review candidates. No approve, edit+approve,
batch approval, rejection, assignment or Employee attempt was performed. Generation was not
repeated after the subsequent read error.

The refresh after generation failed; one read-only retry failed again. Filtered API logs show
Interactive Training readiness HTTP 500 on both reads, while Practice and Final readiness each
return 200. Before generation all three reads returned 200. The frontend loads these readiness
responses with `Promise.all` and retains its old readiness state on failure, explaining why
pre-generation processing/0-of-0 values remain visible. Those values are stale, not proof of
current assessment configuration or missing published lessons.

Static diagnosis: `get_interactive_training_readiness` in `backend/app/services/question_review.py`
selects every published AssessmentVersion for the Training without restricting assessment type.
Generation creates whole-menu Practice and Final rows with null lesson identifiers. The route
then constructs `LessonAssessmentReadinessResponse`, whose lesson identifiers are required UUIDs.
This is a concrete serialization-failure mechanism consistent with the observed 500; a fresh
PostgreSQL regression must verify it before changing production code. Raw provider logs and
customer question content are not copied into this report.

Next corrective boundary: reproduce generation followed by lesson-readiness GET with Practice
and Final present; restrict that read to actual Interactive Training assessments; protect adjacent
Practice/Final and tenant/version behavior. Keep the frontend's stale readiness presentation as
an explicit adjacent finding. Implementation and delivery require their bounded correction scope;
this task has not changed code or deployed a fix. Candidate review/publication remains incomplete.
