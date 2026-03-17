---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 023 Use Cases

## SUC-001: Parallel Ticket Execution
Parent: none (new capability)

- **Actor**: Project-manager agent (controller)
- **Preconditions**: Sprint has multiple tickets, some are independent
  (no shared files, no dependency edges)
- **Main Flow**:
  1. Project-manager analyzes ticket dependencies and file overlap
  2. Identifies groups of independent tickets that can run in parallel
  3. For each independent ticket, creates a git worktree
  4. Dispatches a subagent into each worktree (using dispatch-subagent)
  5. Waits for all subagents to complete
  6. Reviews each subagent's output (two-stage review)
  7. Merges worktree branches back to sprint branch
  8. Cleans up worktrees
  9. Dependent tickets execute sequentially after parallel group
- **Postconditions**: Independent tickets completed in parallel,
  results merged, worktrees cleaned up
- **Acceptance Criteria**:
  - [ ] Skill defines independence analysis criteria
  - [ ] Worktrees created with naming convention
  - [ ] Subagents dispatched into isolated worktrees
  - [ ] Merge and cleanup procedure defined
  - [ ] Conflict resolution procedure defined

## SUC-002: Worktree Lifecycle Management
Parent: none (new instruction)

- **Actor**: Any agent managing worktrees
- **Preconditions**: Parallel execution requested
- **Main Flow**:
  1. Create worktree: `git worktree add <path> -b <branch>`
  2. Naming: `worktree-ticket-NNN` directory, branch per ticket
  3. After subagent completes, merge branch back to sprint branch
  4. Remove worktree: `git worktree remove <path>`
  5. If merge conflict: stop, report conflict, let agent resolve
     manually or fall back to sequential
- **Postconditions**: Worktrees created, used, merged, and cleaned up
- **Acceptance Criteria**:
  - [ ] Naming convention documented
  - [ ] Cleanup procedure documented
  - [ ] Conflict resolution procedure documented
  - [ ] Fallback to sequential on conflict
