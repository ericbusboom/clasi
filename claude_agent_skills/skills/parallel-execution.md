---
name: parallel-execution
description: Executes independent sprint tickets in parallel using git worktrees for filesystem isolation — opt-in only, sequential remains the default
---

# Parallel Execution Skill

This skill enables concurrent execution of independent tickets within a
sprint. Each ticket runs in its own git worktree, providing full filesystem
isolation. A controller agent orchestrates dispatch, review, and merge.

**This is opt-in only.** Sequential execution remains the safe default.
The stakeholder or project-manager must explicitly choose parallel mode.

## Prerequisites

- An active sprint with the execution lock acquired
- Multiple tickets in `todo` status with no dependency edges between them
- The **dispatch-subagent** skill available for spawning subagents
- The **worktree-protocol** instruction loaded for naming and cleanup rules

## Inputs

- The active sprint ID
- The set of `todo` tickets to evaluate for parallel execution

## Process

### 1. Analyze Ticket Independence

Before dispatching in parallel, verify that tickets are truly independent.
Two tickets are independent if and only if **both** conditions hold:

1. **No dependency edges**: Neither ticket appears in the other's
   `depends-on` list, and they share no transitive dependency that is
   not yet `done`.
2. **No overlapping file modifications**: The tickets' plans (or
   descriptions, if no plan exists) do not list any of the same files
   in their "files to create or modify" sections.

**How to check file overlap**:
- Read each ticket's plan file (`NNN-slug-plan.md`). Look at the
  "Files to create or modify" section.
- If no plan exists, read the ticket description and acceptance criteria
  to infer which files will be touched.
- If two tickets both modify the same file, they are **not independent**
  and must run sequentially.

**Grouping result**:
- **Parallel group**: Tickets that are independent of each other.
- **Sequential remainder**: Tickets that depend on parallel-group tickets
  or share file modifications with them. These run after the parallel
  group completes.

If only one ticket is independent (or all tickets have dependencies),
fall back to normal sequential execution — parallel adds overhead with
no benefit for a single ticket.

### 2. Create Worktrees

For each ticket in the parallel group, create a git worktree. Follow the
naming conventions in the **worktree-protocol** instruction:

```bash
# From the sprint branch, create a per-ticket branch and worktree
git worktree add ../worktree-ticket-NNN sprint/NNN-slug -b ticket-NNN-slug
```

- The worktree directory is `../worktree-ticket-NNN` (sibling of the
  main working directory).
- The branch is `ticket-NNN-slug`, forked from the current sprint branch.

Verify each worktree was created successfully before proceeding.

### 3. Dispatch Subagents

For each worktree, use the **dispatch-subagent** skill to spawn a
subagent that will execute the ticket:

- **Working directory**: The worktree path (`../worktree-ticket-NNN`).
- **Task**: Execute the ticket using the **execute-ticket** skill.
- **Context**: Provide the ticket ID, sprint ID, and any relevant
  context the subagent needs.

All subagents run concurrently. The controller waits for all to complete.

### 4. Review Results

After all subagents complete:

1. Check each subagent's exit status. If any failed, note the failure.
2. For each successful subagent, verify:
   - Tests pass in the worktree.
   - The ticket's acceptance criteria are met.
   - The commit history is clean and follows git-workflow conventions.

If a subagent failed, its ticket reverts to `todo` and will be retried
in sequential mode after the parallel group is merged.

### 5. Merge Worktree Branches

Merge each successful ticket branch back to the sprint branch:

```bash
# On the sprint branch
git merge ticket-NNN-slug --no-ff -m "merge: ticket #NNN into sprint branch"
```

**Merge order**: Merge tickets one at a time. After each merge, check
for conflicts before proceeding to the next.

**Conflict resolution**: If a merge produces conflicts despite the
independence analysis, **stop**. Do not attempt automatic resolution.
Instead:
1. Abort the merge (`git merge --abort`).
2. Log the conflict: which files conflicted and which tickets are
   involved.
3. Fall back to sequential execution for the conflicting ticket.
4. Report the unexpected conflict to the controller for investigation
   — the independence analysis missed a shared file.

### 6. Cleanup Worktrees

After all merges are complete (or after falling back to sequential):

```bash
# Remove each worktree
git worktree remove ../worktree-ticket-NNN

# Delete the per-ticket branch (now merged)
git branch -d ticket-NNN-slug
```

**Never leave worktrees dangling.** Even if a ticket failed or was
deferred to sequential execution, remove its worktree. The cleanup
must happen regardless of success or failure.

### 7. Execute Sequential Remainder

If any tickets were deferred (due to dependencies, file overlap, or
merge conflicts), execute them now in normal sequential order using the
standard **execute-ticket** skill on the sprint branch.

## When NOT to Use Parallel Execution

- **Single ticket sprints**: No benefit, just overhead.
- **All tickets have dependencies**: The dependency chain forces
  sequential execution.
- **Tickets modify shared files**: File overlap makes parallel unsafe.
- **Small sprints (2-3 quick tickets)**: The overhead of creating
  worktrees may exceed the time saved.
- **When the stakeholder has not opted in**: Never parallelize by
  default.

## Output

- All parallel-group tickets executed, reviewed, and merged to the
  sprint branch
- Worktrees removed, per-ticket branches deleted
- Sequential-remainder tickets executed on the sprint branch
- Sprint ready for close-sprint when all tickets are done
