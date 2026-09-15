# HoReCa Git Workflow

Current source, publication and delivery evidence lives in [STATUS](../STATUS.md). This file defines the working rules, not a release ledger. [Historical snapshots](../docs/history/harness-checkpoints-through-2026-09-15.md) are retained for evidence only.

## Mandatory rules

- Resolve the repository root and inspect `git status --short --branch` before any Git action.
- Preserve unrelated and user-authored files.
- Define the bounded task's ordered commit map before implementation starts.
- Never use `git add .`; stage only the exact reviewed paths declared for the current map entry.
- Do not commit unless Denys has explicitly authorized local commits for the bounded task and its
  agreed map.
- Push, PR, merge, deploy, remote configuration, and history rewriting are independent approval
  gates. Local-commit authorization grants none of them.
- Do not use destructive Git commands to simplify the worktree.
- Treat accepted checkpoint commits as recoverable project history, not disposable snapshots.

## Commit map contract

Before implementation, write an ordered map whose every entry includes:

1. one coherent behavior or documentation/process outcome;
2. expected production, test, migration, configuration, and directly corresponding documentation
   paths, as applicable;
3. the focused verification that proves the stage is GREEN;
4. an intended descriptive commit message;
5. dependencies on earlier map entries and the remaining excluded scope.

Commit boundaries follow coherent behavior, not file count, elapsed time, token budget, or
arbitrary diff size. Code, focused tests, migrations, and directly corresponding documentation
stay together when they are required for one behavior. Independently useful or reversible
outcomes use separate map entries.

The map may change when implementation evidence reveals a different coherent boundary. Record
the reason, update the remaining map before continuing, and do not use the change to expand the
bounded Linear scope silently.

## Local-commit authorization

One explicit authorization for local commits in a bounded Linear issue covers all selective
commits in that issue's agreed map. The agent does not ask again before every mapped commit.

That authorization does not permit:

- paths or behavior outside the bounded issue and map;
- push, PR, merge, release, Railway, or deployment;
- remote creation or reconfiguration;
- squash, amend, rebase, reset, force-push, or another history rewrite.

If local commits are not authorized, preserve the same logical boundaries in the worktree and
report an exact selective staging plan for every proposed commit. Do not change the Git index.

## GREEN checkpoint sequence

For every mapped implementation stage:

1. produce and record the smallest meaningful failing `RED` test when behavior changes;
2. confirm RED fails because the intended behavior is missing, not because setup is broken;
3. implement the smallest coherent change to reach `GREEN`;
4. refactor while the focused and proportionate adjacent checks remain green;
5. run the verification declared by the map entry;
6. inspect the exact diff for scope, secrets, local paths, generated artifacts, and unrelated
   changes;
7. when local commits are authorized, selectively stage the declared paths, verify the staged
   inventory and `git diff --cached --check`, then create one atomic commit;
8. confirm the remaining worktree still matches the uncompleted map before starting the next
   independent stage.

A broken RED state is evidence, not a checkpoint: never commit it knowingly. Documentation-only
work may use its declared TDD exception and documentation verification instead, but it becomes a
commit checkpoint only after those checks pass.

## Checkpoint preservation and recovery

Do not squash, amend, rebase, reset, or otherwise rewrite an accepted checkpoint commit without
separate Denys approval. Once history is shared, recover a bad checkpoint with a new revert or
corrective commit so the earlier state remains reachable and auditable.

An unaccepted local checkpoint may still be corrected only within the current explicit authority;
never infer history-rewrite permission from permission to commit.

## Protected material and publication boundary

- `Photos/` is protected CRA-19 material. Do not modify, move, ignore, stage or publish it unless
  the approved bounded asset map explicitly includes it.
- `.venv`, `.env*`, caches, installers, runtime output and local acceptance helpers are not
  publication content. Preserve unrelated changes in every worktree.
- A deployed source packet and a Git commit may differ. Compare the exact manifest before
  choosing a release candidate; preserve already deployed fixes during reconciliation.
- Publication does not authorize the next stage. Follow the active bounded Linear issue,
  agreed map and existing explicit authorization; push, PR, merge, history rewrite, provider,
  deployment and non-test data operations retain their separate gates.
