# HoReCa Git Workflow

## Current baseline state

The repository is on `main`. The published history contains the accepted Stage 0 repository
baseline and accepted Stage 1 identity-persistence checkpoint. CRA-30 adds the approved five-part
local Stage 2 commit sequence; its acceptance and publication remain separate gates. `origin`
points to the approved HoReCa GitHub repository, and local `main` has upstream tracking.

HoReCa's project-local `.harness/` is intentional tracked repository documentation adapted from
the pinned global Denys Agent Harness. The global harness itself is not vendored, committed, or
pushed from this repository. `Photos/` remains deferred CRA-19 project material: it is untracked,
unstaged, and outside the published backend/docs baseline.

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

## Published baseline boundary

The initial published backend/docs baseline contains the 43 paths accepted in the five-commit
CRA-23 map, plus the later documentation-only repository-state synchronization checkpoint. The
baseline intentionally excludes:

1. `Photos/`, which contains CRA-19 homepage project assets and remains untouched, unignored, and
   unstaged unless a separate approved map explicitly includes those assets;
2. local artifacts such as `.venv`, `.pydeps`, `.env*`, caches, coverage files, installers, and
   acceptance helpers, which are never baseline content.

Publication of any checkpoint does not authorize the next implementation stage. Every subsequent
change still requires an active bounded Linear issue, an agreed commit map, and the applicable
local-commit and remote-action approvals. Stage 1 is accepted; the current Stage 2 state must be
resolved through Linear START HERE and CRA-30 evidence rather than this workflow summary.
