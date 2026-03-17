---
name: worktree-protocol
description: Operational rules for git worktree management during parallel ticket execution — naming, cleanup, and conflict resolution
---

# Worktree Protocol

This instruction defines the operational rules for using git worktrees
during parallel ticket execution. All agents creating or working in
worktrees must follow these rules.

## When Worktrees Are Used

Worktrees are used only during parallel ticket execution (see the
**parallel-execution** skill). They provide filesystem isolation so
multiple subagents can work on different tickets simultaneously without
interfering with each other.

Worktrees are **never** used for sequential ticket execution. The
standard execute-ticket workflow operates directly on the sprint branch.

## Naming Conventions

### Worktree Directories

Worktree directories are created as siblings of the main working
directory, named by ticket number:

```
worktree-ticket-NNN
```

Examples:
- `worktree-ticket-001`
- `worktree-ticket-002`
- `worktree-ticket-005`

The directory is always relative to the parent of the main working
directory (i.e., `../worktree-ticket-NNN` from the project root).

### Per-Ticket Branches

Each worktree checks out a dedicated branch forked from the sprint
branch:

```
ticket-NNN-slug
```

Examples:
- `ticket-001-add-auth-endpoint`
- `ticket-002-update-user-model`
- `ticket-005-fix-validation`

The slug is derived from the ticket title, following the same
conventions as sprint branch slugs (lowercase, hyphens, no special
characters).

### Creation Command

```bash
git worktree add ../worktree-ticket-NNN sprint/NNN-slug -b ticket-NNN-slug
```

This creates the worktree directory and a new branch in one step. The
branch starts from the current sprint branch HEAD.

## Cleanup Rules

### After Successful Merge

Once a ticket branch has been merged back to the sprint branch:

1. Remove the worktree:
   ```bash
   git worktree remove ../worktree-ticket-NNN
   ```
2. Delete the per-ticket branch:
   ```bash
   git branch -d ticket-NNN-slug
   ```

### After Failure or Fallback

If a ticket fails, is deferred, or falls back to sequential execution,
the worktree must still be cleaned up:

1. Remove the worktree:
   ```bash
   git worktree remove ../worktree-ticket-NNN --force
   ```
   The `--force` flag is needed if the worktree has uncommitted changes.
2. Delete the per-ticket branch:
   ```bash
   git branch -D ticket-NNN-slug
   ```
   Use `-D` (force delete) since the branch was not merged.

### Never Leave Worktrees Dangling

A dangling worktree is one that exists on disk but is no longer needed.
Dangling worktrees:
- Waste disk space (full copy of the working tree).
- Cause confusion about which directory is the "real" working directory.
- Block future worktree creation if the branch is still checked out.

After parallel execution completes (whether successfully or not), verify
no worktrees remain:

```bash
git worktree list
```

The output should show only the main working directory. If any
`worktree-ticket-*` entries remain, remove them.

## Conflict Resolution

### Expected: No Conflicts

The independence analysis in the **parallel-execution** skill is
designed to ensure that parallel tickets do not modify the same files.
If the analysis is correct, merges should be conflict-free.

### Unexpected Conflicts

If a merge conflict occurs despite the independence analysis:

1. **Do not attempt automatic resolution.** The conflict means the
   independence analysis missed a shared file or an indirect dependency.
   Automatic resolution risks introducing subtle bugs.

2. **Abort the merge immediately**:
   ```bash
   git merge --abort
   ```

3. **Log the conflict**: Record which files conflicted, which tickets
   are involved, and why the independence analysis missed it. This
   information helps improve future analysis.

4. **Fall back to sequential execution** for the conflicting ticket:
   - Remove the conflicting ticket's worktree (see cleanup rules above).
   - Execute the ticket sequentially on the sprint branch after the
     other parallel tickets have been merged.

5. **Report to the controller**: The project-manager (or whoever is
   orchestrating) should be notified of the unexpected conflict so they
   can decide whether to adjust the remaining tickets' execution order.

### Preventing Conflicts

To minimize the risk of unexpected conflicts:

- Be thorough in the independence analysis. Check not just the files
  listed in ticket plans, but also generated files, configuration files,
  and shared test fixtures.
- When in doubt, run tickets sequentially. The cost of a false negative
  (conflict during merge) is higher than the cost of a false positive
  (unnecessary sequential execution).
- If two tickets both touch "shared" files (e.g., `__init__.py`,
  configuration files, shared type definitions), treat them as dependent
  even if the changes are in different parts of the file.

## Worktree Lifecycle Summary

```
1. Independence analysis → identify parallel group
2. git worktree add ../worktree-ticket-NNN ... → create worktrees
3. Dispatch subagents → execute tickets in worktrees
4. Subagents complete → review results
5. git merge ticket-NNN-slug → merge back to sprint branch
6. git worktree remove ../worktree-ticket-NNN → cleanup
7. git branch -d ticket-NNN-slug → delete merged branch
```

All seven steps must complete for each ticket in the parallel group.
If any step fails, the cleanup steps (6-7) must still run.
