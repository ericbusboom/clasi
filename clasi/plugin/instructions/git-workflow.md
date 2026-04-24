---
name: git-workflow
description: Instructions for how agents interact with git during ticket execution — commits, messages, branches, and safety rules
---

# Git Workflow

## Core Rule

All work must be committed to git. Code that exists only in a conversation
context can be lost when the session ends. Commit early, commit with purpose.

## When to Commit

- **At ticket completion** (required): Before marking a ticket done, commit
  all changes from that ticket. This is the minimum.
- **At significant milestones** (recommended): If a ticket involves multiple
  substantial steps (e.g., implementing a module, then writing its tests),
  commit after each milestone. This protects against context window loss.
- **Never commit broken code**: All tests must pass before committing. If
  tests are failing, fix them first.

## Commit Message Format

Use conventional-style messages that reference the ticket ID and sprint:

```
<type>: <short summary> (#NNN, sprint NNN)

<optional body explaining why, not what>
```

If not working within a sprint, omit the sprint reference:

```
<type>: <short summary> (#NNN)
```

**Types**:
- `feat` — New feature or capability
- `fix` — Bug fix
- `refactor` — Code restructuring without behavior change
- `docs` — Documentation only
- `test` — Adding or updating tests
- `chore` — Maintenance tasks (deps, config, tooling)

**Examples**:
```
feat: add user authentication endpoint (#003, sprint 001)
fix: handle empty input in parser (#007, sprint 002)
docs: update architecture for new scope (#010)
test: add golden file tests for report generator (#005, sprint 001)
chore: update dependencies to latest versions (#012)
```

The ticket ID and sprint number make commits traceable to their work items.

## Branch Strategy

### Sprint Branches (Recommended)

When using sprints, create one branch per sprint:

```
git checkout -b sprint/NNN-slug
```

All ticket work within the sprint is committed to the sprint branch. When
the sprint is complete and validated, the branch is merged back to main.

- Branch created at sprint start (by the plan-sprint skill)
- All ticket commits go to the sprint branch
- Branch merged to main at sprint close (by the close-sprint skill)
- No feature branches within a sprint — tickets commit directly to the
  sprint branch

### Option A: Work on Main (for projects not using sprints)

Commit directly to the main branch. Simple, no merge overhead. Appropriate
when there is one developer or one AI agent working at a time and sprints
are not in use.

### Option B: Feature Branches (for projects not using sprints)

Create a branch per ticket:

```
git checkout -b ticket/NNN-slug
```

Merge back to main when the ticket is complete. Use this when multiple
people or agents work in parallel, or when you want PR-based review.

Choose one approach and document it in the project's README or contributing
guide. If no choice is documented and sprints are in use, use sprint
branches. Otherwise, default to working on main.

## Closing a Sprint Branch

Merging a sprint branch is **not** the same as closing a sprint. The merge
is one step in a multi-step atomic operation. When a sprint is complete:

1. Merge the sprint branch to main.
2. Move the sprint directory to `docs/clasi/sprints/done/`.
3. Update the sprint's `status` to `done` in `sprint.md` frontmatter.
4. Delete the local sprint branch.
5. Commit the sprint closure (the directory move and status update).

**Never merge a sprint branch without also archiving the sprint directory.**
A merged branch with an active sprint directory is an inconsistent state.
Use the **close-sprint** skill to perform all steps together.

## Commit Timing

These rules ensure every commit in the git history represents a known-good
test state. This makes `git bisect` reliable and rollbacks safe.

1. **Always run tests before committing.** Run `uv run pytest` (or the
   project's equivalent) and confirm all tests pass before creating a
   commit. No exceptions for "I'm pretty sure it's fine."

2. **Do not commit with failing tests** unless you are on a feature branch
   and prefix the commit message with `WIP:`. WIP commits are never
   allowed on `main` or `master`. They exist only to checkpoint work on a
   branch that will be squashed or rebased before merge. Example:
   ```
   WIP: partial implementation of auth middleware (#003, sprint 001)
   ```

3. **During TDD: commit immediately after the green phase** (before
   refactoring). Once all tests pass, commit that state. This captures
   the minimal working implementation and makes it easy to revert a
   refactor that goes wrong.

4. **After refactoring: run tests again and commit the refactor
   separately.** The refactor commit is distinct from the green-phase
   commit. If a refactor breaks something, you can revert it without
   losing the working implementation.

5. **Each commit should represent a known-good test state.** Combined
   with rules 1-4, this means the git log is a sequence of verified
   snapshots. Any commit can be checked out and tested with confidence.

See the **tdd-cycle** skill for details on how commit points integrate
with the red-green-refactor cycle.

## Version Bumping

After every substantive commit, run `clasi version bump` to advance the
project version. Rationale: tools are installed editable (`pipx install -e`
or `uv pip install -e`), so `clasi --version` is how a session tells which
code it's actually running. If the version never changes, you can't tell
whether your edit is live.

- **After each commit**: run `clasi version bump` (no flags). This updates
  the version source file. Commit that change too (a one-line follow-up
  commit is fine: `chore: bump version`).
- **When finishing a branch**: `close_sprint` bumps and tags automatically
  at sprint close — do not bump manually immediately before it. For
  non-sprint branches, run `clasi version bump --tag` before merging.
- **On OOP commits direct to master**: bump after every commit.
- **Don't batch**: one bump per commit keeps `git bisect` and "is my
  change live?" checks honest.

## Safety Rules

- **Never force-push** unless explicitly instructed by the human.
- **Never skip hooks** (`--no-verify`) unless explicitly instructed.
- **Never rewrite published history** (amend, rebase on pushed commits).
- **Never commit secrets** (.env files, API keys, credentials). Check
  `.gitignore` before committing.
- **Always check `git status`** before committing to avoid including
  unintended files.

## Relationship to Tickets and Sprints

- A ticket is not done until its changes are committed.
- The commit message must reference the ticket ID.
- If working within a sprint, the commit message must also reference the
  sprint number.
- If a ticket requires multiple commits (milestones), each commit should
  reference the same ticket ID and sprint number.
- When completing a ticket, the final commit should include the ticket file
  move to `done/` and any frontmatter updates.
